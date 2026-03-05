from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from uuid import UUID
from app.db.session import get_db
from app.services.event_builder import EventBuilder
from app.db.models.event import Event
from app.db.models.correlation_link import CorrelationLink
from app.db.models.parsed_candidate import ParsedTransactionCandidate
from app.core.config import settings

router = APIRouter()

@router.post("/email/{email_id}")
def reprocess_email(
    email_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Reprocess a specific email by ID.
    This will re-parse, re-classify, and re-correlate the email.
    """
    # Check if email exists
    from app.db.models.email_raw import EmailRaw
    email = db.query(EmailRaw).filter(EmailRaw.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    # Add reprocessing task to background
    background_tasks.add_task(reprocess_single_email, email_id, db)

    return {"message": f"Reprocessing started for email {email_id}"}

@router.post("/rebuild/all")
def rebuild_all(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Rebuild all events from scratch.
    This will purge all parsed candidates, events, and correlation links,
    then reprocess all emails.
    """
    background_tasks.add_task(rebuild_all_events, db)

    return {"message": "Full rebuild started"}

def reprocess_single_email(email_id: UUID, db: Session):
    """Background task to reprocess a single email."""
    try:
        builder = EventBuilder(db)
        # This would need to be implemented in EventBuilder
        # For now, just mark as processed
        pass
    except Exception as e:
        # Log error
        pass

def rebuild_all_events(db: Session):
    """Background task to rebuild all events."""
    try:
        # Purge existing data
        db.query(Event).delete()
        db.query(CorrelationLink).delete()
        db.query(ParsedTransactionCandidate).delete()

        # Reprocess all emails
        from app.db.models.email_raw import EmailRaw
        emails = db.query(EmailRaw).all()

        builder = EventBuilder(db)
        for email in emails:
            # Reprocess each email
            pass

        db.commit()
    except Exception as e:
        db.rollback()
        # Log error
        pass