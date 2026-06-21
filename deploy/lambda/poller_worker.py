import boto3, json, os
from app.gmail.poller import GmailPoller

def load_secret(secret_id):
    sm = boto3.client("secretsmanager")
    return json.loads(sm.get_secret_value(SecretId=secret_id)["SecretString"])

def lambda_handler(event, context):
    creds = load_secret(os.environ["GMAIL_CREDS_ID"])
    token = load_secret(os.environ["GMAIL_TOKEN_ID"])
    db_url = load_secret(os.environ["DATABASE_URL_ID"])

    poller = GmailPoller(
        gmail_creds=creds,
        gmail_token=token,
        sqlite_path=os.environ["SQLITE_PATH"],
        database_url=db_url,
    )
    poller.poll_once()
    return {"status": "poll_completed"}
