import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from app.core.config import settings

# Minimum scope needed to read Gmail messages
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def load_credentials() -> Credentials:
    token_path = settings.GMAIL_TOKEN_PATH
    creds = None

    # Load existing token
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # Refresh token if expired
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    # First-time OAuth flow
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            settings.GMAIL_CREDENTIALS_PATH, SCOPES
        )
        creds = flow.run_local_server(port=0)

        # Persist token
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return creds