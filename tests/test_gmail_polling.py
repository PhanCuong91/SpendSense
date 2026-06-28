import base64
import json
import os
from email.message import EmailMessage

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import app.gmail.auth as gmail_auth
import app.gmail.poller as gmail_poller
from app.core.config import settings
from app.gmail.client import GmailClient


class DummyCreds:
    def __init__(self, valid=True, expired=False, refresh_token=None):
        self.valid = valid
        self.expired = expired
        self.refresh_token = refresh_token

    def refresh(self, request):
        self.expired = False

    def to_json(self):
        return "{}"


def test_load_credentials_prefers_token_json(monkeypatch):
    monkeypatch.setattr(settings, "GMAIL_TOKEN_JSON", json.dumps({"token": "abc"}))
    monkeypatch.setattr(settings, "GMAIL_TOKEN_PATH", "/tmp/token.json")
    monkeypatch.setattr(settings, "GMAIL_CREDENTIALS_JSON", None)

    captured = {}

    def fake_from_authorized_user_info(info, scopes):
        captured["info"] = info
        captured["scopes"] = scopes
        return DummyCreds(valid=True)

    monkeypatch.setattr(gmail_auth.os.path, "exists", lambda _path: False)
    monkeypatch.setattr(
        gmail_auth.Credentials,
        "from_authorized_user_info",
        fake_from_authorized_user_info,
    )
    monkeypatch.setattr(
        gmail_auth.Credentials,
        "from_authorized_user_file",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("file path should not be used")),
    )

    creds = gmail_auth.load_credentials()

    assert creds.valid is True
    assert captured["info"]["token"] == "abc"
    assert captured["scopes"] == gmail_auth.SCOPES


def test_load_credentials_runs_oauth_flow_when_needed(monkeypatch, tmp_path):
    token_path = tmp_path / "token.json"
    monkeypatch.setattr(settings, "GMAIL_TOKEN_JSON", None)
    monkeypatch.setattr(settings, "GMAIL_TOKEN_PATH", str(token_path))
    monkeypatch.setattr(settings, "GMAIL_CREDENTIALS_JSON", json.dumps({"installed": {"client_id": "id"}}))

    created = {}

    class FakeFlow:
        def __init__(self, *_args, **_kwargs):
            created["called"] = True

        def run_local_server(self, port=0):
            created["port"] = port
            return DummyCreds(valid=True)

    monkeypatch.setattr(gmail_auth.os.path, "exists", lambda _path: False)
    monkeypatch.setattr(
        gmail_auth.InstalledAppFlow,
        "from_client_config",
        lambda client_config, scopes: FakeFlow(client_config, scopes),
    )

    creds = gmail_auth.load_credentials()

    assert creds.valid is True
    assert created["called"] is True
    assert created["port"] == 0
    assert token_path.exists()


def test_gmail_client_decode_email_returns_subject_and_body():
    client = GmailClient.__new__(GmailClient)
    message = EmailMessage()
    message["Subject"] = "Test Subject"
    message.set_content("Plain body")

    raw_data = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    raw_payload = {"headers": [{"name": "Subject", "value": "Test Subject"}], "body": {"data": raw_data}}

    subject, body = client.decode_email(raw_payload, "msg-1")

    assert subject == "Test Subject"
    assert body.strip() == "Plain body"


def test_gmail_poller_get_subject_extracts_header(monkeypatch):
    poller = gmail_poller.GmailPoller.__new__(gmail_poller.GmailPoller)

    monkeypatch.setattr(gmail_poller, "urlsafe_b64decode", lambda payload: b"Subject: Hello world", raising=False)
    monkeypatch.setattr(gmail_poller, "message_from_bytes", lambda data: {"Subject": "Hello world"}, raising=False)

    assert poller.get_subject("encoded") == "Hello world"


def test_gmail_poller_poll_once_ingests_bank_email(monkeypatch):
    class FakeInspector:
        def has_table(self, _name):
            return True

    class FakeQuery:
        def __init__(self, existing):
            self.existing = existing

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return self.existing

    class FakeSession:
        def __init__(self):
            self.added = []
            self.committed = False
            self.closed = False

        def query(self, _model):
            return FakeQuery(None)

        def add(self, row):
            row.id = 42
            self.added.append(row)

        def commit(self):
            self.committed = True

        def close(self):
            self.closed = True

    fake_session = FakeSession()
    enqueued_ids = []

    class FakeClient:
        def list_messages(self, query, page_token=None):
            return {"messages": [{"id": "msg-1"}]}

        def get_message(self, msg_id):
            return {
                "internalDate": "1710000000000",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "mailalert@acb.com.vn"},
                        {"name": "Subject", "value": "Bank Alert"},
                    ]
                },
            }

        def decode_email(self, raw_payload, msg_id):
            return "Bank Alert", "Body"

    monkeypatch.setattr(gmail_poller, "SessionLocal", lambda: fake_session)
    monkeypatch.setattr(gmail_poller, "inspect", lambda _engine: FakeInspector())
    monkeypatch.setattr(gmail_poller, "enqueue_for_parsing", lambda email_id: enqueued_ids.append(email_id))

    poller = gmail_poller.GmailPoller.__new__(gmail_poller.GmailPoller)
    poller.client = FakeClient()

    poller.poll_once()

    assert len(fake_session.added) == 1
    assert fake_session.committed is True
    assert fake_session.added[0].gmail_message_id == "msg-1"
    assert fake_session.added[0].from_email == "mailalert@acb.com.vn"
    assert fake_session.closed is True
    assert enqueued_ids == [42]