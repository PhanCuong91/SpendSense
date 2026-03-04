from googleapiclient.discovery import build
from base64 import urlsafe_b64decode
from email import message_from_bytes
from app.gmail.auth import load_credentials
from app.core.logging import get_logger

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

    def decode_email(self, raw_payload):
        """Convert Gmail message payload to subject + body text."""
        data = urlsafe_b64decode(raw_payload.encode("UTF-8"))
        email_msg = message_from_bytes(data)

        subject = email_msg.get("Subject", "")
        body = ""

        if email_msg.is_multipart():
            for part in email_msg.walk():
                ctype = part.get_content_type()
                if ctype == "text/plain":
                    body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
        else:
            body = email_msg.get_payload(decode=True).decode("utf-8", errors="ignore")

        return subject, body
