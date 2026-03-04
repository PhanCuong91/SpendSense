from app.db.session import SessionLocal
from app.db.models.email_raw import EmailRaw
from app.db.models.parsed_candidate import ParsedTransactionCandidate
from app.parsing.parser import parse_email
from app.core.logging import get_logger
from app.services.event_builder import EventBuilder

logger = get_logger(__name__)


def enqueue_for_parsing(email_id):
    """Direct synchronous parsing for now. Replace with RQ/Celery later."""
    parse_email_task(email_id)


def parse_email_task(email_id):
    session = SessionLocal()
    try:
        email = session.query(EmailRaw).filter(EmailRaw.id == email_id).first()
        if not email:
            logger.error(f"Email {email_id} not found for parsing")
            return

        parsed = parse_email(email.subject, email.body)

        row = ParsedTransactionCandidate(
            email_id=email.id,
            amount=parsed["amount"],
            currency=parsed["currency"],
            datetime_sgt=parsed["datetime_sgt"],
            inferred_sender=parsed["inferred_sender"],
            inferred_receiver=parsed["inferred_receiver"],
            raw_reference=parsed["raw_reference"],
            debit_credit=parsed["debit_credit"],
            classification_hint=None,
        )

        session.add(row)
        session.commit()
        
        # After session.commit() for ParsedTransactionCandidate:
        EventBuilder().process_candidate(row.id)

        logger.info(f"Parsed email → ParsedTransactionCandidate {row.id}")

    except Exception as e:
        logger.error(f"Parser error: {e}")
        session.rollback()
        raise

    finally:
        session.close()