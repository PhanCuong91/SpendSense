import traceback
from datetime import datetime, timezone
from app.gmail.client import GmailClient
from app.db.session import SessionLocal
from app.db.models.email_raw import EmailRaw
from app.workers.parser_worker import enqueue_for_parsing
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class GmailPoller:
    QUERY = "newer_than:3d"   # configurable Gmail search query

    def __init__(self):
        self.client = GmailClient()

    def poll_once(self):
        logger.info("Starting Gmail poll cycle…")

        session = SessionLocal()
        try:
            page_token = None
            while True:
                response = self.client.list_messages(self.QUERY, page_token)

                if "messages" not in response:
                    logger.info("No Gmail messages found for this cycle.")
                    break

                for msg in response["messages"]:
                    msg_id = msg["id"]

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

                    internal_ts = int(full_msg.get("internalDate", 0)) / 1000
                    internal_date = datetime.fromtimestamp(
                        internal_ts, tz=timezone.utc
                    )

                    # Extract payload
                    parts = full_msg.get("payload", {}).get("parts", [])
                    if not parts:
                        logger.warning(f"No parts found for message {msg_id}")
                        continue

                    raw_data = parts[0]["body"].get("data")
                    if not raw_data:
                        logger.warning(f"No data encoded for {msg_id}")
                        continue

                    subject, body = self.client.decode_email(raw_data)

                    # Store into DB
                    email_row = EmailRaw(
                        gmail_message_id=msg_id,
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