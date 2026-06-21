from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.session import get_db
from app.schemas.event_schema import EventOut
from app.db.models.event import Event
from app.core.config import settings

router = APIRouter()

@router.get("", response_model=List[EventOut])
def get_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    event_type: Optional[str] = None,
    sender: Optional[str] = None,
    receiver: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get events with optional filtering and pagination.
    """
    query = db.query(Event)

    if event_type:
        query = query.filter(Event.event_type == event_type)
    if sender:
        query = query.filter(Event.sender == sender)
    if receiver:
        query = query.filter(Event.receiver == receiver)

    events = query.offset(skip).limit(limit).all()
    return events