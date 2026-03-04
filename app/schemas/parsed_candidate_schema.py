from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ParsedCandidateOut(BaseModel):
    id: str
    email_id: str
    amount: Optional[float]
    currency: Optional[str]
    datetime_sgt: Optional[datetime]
    inferred_sender: Optional[str]
    inferred_receiver: Optional[str]
    raw_reference: Optional[str]
    debit_credit: Optional[str]