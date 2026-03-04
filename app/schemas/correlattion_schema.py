from pydantic import BaseModel


class CorrelationLinkOut(BaseModel):
    id: str
    debit_candidate_id: str
    credit_candidate_id: str
    event_id: str