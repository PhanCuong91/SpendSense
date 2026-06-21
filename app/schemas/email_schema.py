from pydantic import BaseModel
from datetime import datetime


class EmailRawOut(BaseModel):
    id: str
    gmail_message_id: str
    from_email: str
    subject: str
    body: str
    internal_date: datetime
    received_at: datetime