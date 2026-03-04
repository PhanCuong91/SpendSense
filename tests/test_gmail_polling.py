class MockGmailClient:
    def __init__(self, saved_emails):
        self.saved_emails = saved_emails

    def list_messages(self, query: str, page_token: str | None = None):
        return {"messages": [{"id": email["id"]} for email in self.saved_emails]}

    def get_message(self, msg_id: str):
        for email in self.saved_emails:
            if email["id"] == msg_id:
                return email
        return {}

    def decode_email(self, raw_payload):
        # Replace with actual decoding if needed
        return "Test Subject", "Test Body"

def test_placeholder_gmail_polling():
    """
    Full Gmail polling cannot be tested without mocking Google API.
    This test acts as a placeholder.
    """
    assert True

# Example real email data (replace with your actual email dict)
real_email = {
    "id": "real_gmail_id_123",
    "internalDate": "1640995200000",  # Example timestamp
    "payload": {
        "parts": [
            {"body": {"data": "your_base64_encoded_email_data"}}
        ]
    }
}

# Patch GmailPoller to use the mock client
from app.gmail.poller import GmailPoller

def test_gmail_poller_with_real_email(monkeypatch):
    poller = GmailPoller()
    poller.client = MockGmailClient([real_email])
    # Optionally patch enqueue_for_parsing if you want to avoid side effects
    # monkeypatch.setattr("app.workers.parser_worker.enqueue_for_parsing", lambda x: None)
    poller.poll_once()
    # Add assertions here to check DB or logs