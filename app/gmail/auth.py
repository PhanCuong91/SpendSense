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

    # Prefer secret JSON values when provided via environment / ECS secrets.
    token_json = settings.GMAIL_TOKEN_JSON
    credentials_json = settings.GMAIL_CREDENTIALS_JSON

    if token_json:
        creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    elif os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # Refresh token if expired
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    # First-time OAuth flow
    if not creds or not creds.valid:
        if credentials_json:
            client_config = json.loads(credentials_json)
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                settings.GMAIL_CREDENTIALS_PATH, SCOPES
            )

        creds = flow.run_local_server(port=0)

        # Persist token only when not using secret JSON token input.
        if token_json is None and token_path:
            try:
                with open(token_path, "w") as f:
                    f.write(creds.to_json())
            except OSError:
                pass

    return creds