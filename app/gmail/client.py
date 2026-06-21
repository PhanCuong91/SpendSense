from multiprocessing.util import DEBUG

from googleapiclient.discovery import build
from base64 import urlsafe_b64decode
from email import message_from_bytes
from app.gmail.auth import load_credentials
from app.core.logging import get_logger, save_to_file
from app.core.config import settings

logger = get_logger(__name__)


class GmailClient:
    def __init__(self):
        creds = load_credentials()
        self.service = build("gmail", "v1", credentials=creds)

    def list_messages(self, query: str, page_token: str | None = None):
        return (
            self.service.users()
            .messages()
            .list(userId="me", q=query, pageToken=page_token)
            .execute()
        )

    def get_message(self, msg_id: str):
        return (
            self.service.users()
            .messages()
            .get(userId="me", id=msg_id, format="full")
            .execute()
        )

    def decode_email(self, raw_payload, msg_id):
        # Extract subject from headers
        headers = raw_payload.get("headers", [])
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "") 
        # Extract parts - this is where the email body and attachments info would be
        parts = raw_payload.get('parts', [])
        
        if not parts:
            # Extract body directly if no parts (some emails may not have multipart structure)
            raw_data = raw_payload.get('body', {}).get("data")
        else:
            raw_data = parts[0]["body"].get("data")
        # logger.info(f"Message {msg_id} raw data: {raw_data}")
        if not raw_data:
            return "", ""
        """Convert Gmail message payload to subject + body text."""
        data = urlsafe_b64decode(raw_data.encode("UTF-8"))
        logger.info(f"Decoded raw payload: {data[:100]}...")  # Log first 100 chars of decoded data
        email_msg = message_from_bytes(data)
        # if settings.DEBUG:
        #     save_to_file(email_msg, f"decoded_email_{msg_id}.json")
        body = ""

        if email_msg.is_multipart():
            for part in email_msg.walk():
                ctype = part.get_content_type()
                if ctype == "text/plain":
                    body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
        else:
            body = email_msg.get_payload(decode=True).decode("utf-8", errors="ignore")

        return subject, body
