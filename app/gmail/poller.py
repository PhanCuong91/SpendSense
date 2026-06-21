import traceback
from datetime import datetime, timezone
from app.gmail.client import GmailClient
from app.db.base import Base
from app.db.session import SessionLocal, engine
from sqlalchemy import inspect
# Import models to ensure they're all registered
from app.db.models import EmailRaw
from app.workers.parser_worker import enqueue_for_parsing
from app.core.config import settings
from app.core.logging import get_logger, save_to_file

logger = get_logger(__name__)
bank_emails = ["mailalert@acb.com.vn", "ibanking.alert@dbs.com", "paylah.alert@dbs.com", "from_us@trustbank.sg"]

class GmailPoller:
    QUERY = "newer_than:1d"   # configurable Gmail search query

    def __init__(self):
        self.client = GmailClient()

    def get_subject(self, payload):
        """Extract subject from Gmail message payload."""
        data = urlsafe_b64decode(payload.encode("UTF-8"))
        email_msg = message_from_bytes(data)
        return email_msg.get("Subject", "")

    def from_bank_email(self, sender_email):
        """Check if the email is from a bank based on predefined keywords."""
        for keyword in bank_emails:
            if keyword in sender_email.lower():
                return True
        return False

    def poll_once(self):
        logger.info("Starting Gmail poll cycle…")
        
        # Ensure the `email_raw` table exists; create it if missing.
        try:
            inspector = inspect(engine)
            if not inspector.has_table(EmailRaw.__tablename__):
                Base.metadata.create_all(bind=engine, tables=[EmailRaw.__table__], checkfirst=True)
                logger.info(f"Created missing table {EmailRaw.__tablename__}")
        except Exception as e:
            logger.error(f"Error ensuring table {EmailRaw.__tablename__} exists: {e}")

        session = SessionLocal()
        try:
            page_token = None
            while True:
                response = self.client.list_messages(self.QUERY, page_token)

                if "messages" not in response:
                    logger.info("No Gmail messages found for this cycle.")
                    break
                logger.info(f"Found {len(response['messages'])} messages in this batch.")
                for msg in response["messages"]:
                    msg_id = msg["id"]
                    skip = False
                    # Idempotency check — avoid re-inserting
                    exists = (
                        session.query(EmailRaw)
                        .filter(EmailRaw.gmail_message_id == msg_id)
                        .first()
                    )
                    if exists:
                        continue

                    # Fetch message
                    full_msg = self.client.get_message(msg_id)
                    # if settings.DEBUG:
                        # save_to_file(full_msg, f"full_msg_{msg_id}.json")

                    internal_ts = int(full_msg.get("internalDate", 0)) / 1000
                    internal_date = datetime.fromtimestamp(
                        internal_ts, tz=timezone.utc
                    ).astimezone(datetime.now().astimezone().tzinfo)

                    raw_payload = full_msg.get("payload", {})
                    from_email = next((h["value"] for h in raw_payload.get("headers", []) if h["name"] == "From"), "")

                    if not self.from_bank_email(from_email):
                        # skip the email if it matches any bank keyword in the sender's email address
                        continue
                    subject, body = self.client.decode_email(raw_payload,msg_id)
                    # logger.info(f"Decoded email {msg_id} - Subject: {subject}, Body length: {len(body)}")

                    # Store into DB
                    email_row = EmailRaw(
                        gmail_message_id=msg_id,
                        from_email=from_email,
                        subject=subject,
                        body=body,
                        internal_date=internal_date,
                    )
                    session.add(email_row)
                    session.commit()

                    logger.info(f"Ingested new email: {msg_id}")

                    # Enqueue for parsing (worker will handle it)
                    enqueue_for_parsing(email_row.id)

                page_token = response.get("nextPageToken")
                if not page_token:
                    break

        except Exception as e:
            logger.error(f"Gmail poller error: {e}")
            logger.error(traceback.format_exc())

        finally:
            session.close()

        logger.info("Gmail poll cycle complete.")