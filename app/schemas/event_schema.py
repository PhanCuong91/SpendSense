from typing import List, Optional
from pydantic import BaseModel


class EventOut(BaseModel):
    id: str
    eventType: str
    sender: str
    receiver: str
    amount: Optional[float]
    currency: Optional[str]
    datetime: Optional[str]
    emails: List[str] = []
    description: Optional[str]


class EventListResponse(BaseModel):
    items: List[EventOut]
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool
``