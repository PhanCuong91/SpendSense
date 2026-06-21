from app.db.session import SessionLocal, engine
from app.db.base import Base
from sqlalchemy import inspect
from app.db.models.email_raw import EmailRaw
from app.db.models.parsed_candidate import ParsedTransactionCandidate
from app.parsing.parser import parse_email, extract_plain_text
from app.core.logging import get_logger
from app.services.event_builder import EventBuilder

logger = get_logger(__name__)



def enqueue_for_parsing(email_id):
    """Direct synchronous parsing for now. Replace with RQ/Celery later."""
    parse_email_task(email_id)


def parse_email_task(email_id):

    # Ensure the `parsed_transaction_candidate` table exists; create it if missing.
    try:
        inspector = inspect(engine)
        if not inspector.has_table(ParsedTransactionCandidate.__tablename__):
            Base.metadata.create_all(bind=engine, tables=[ParsedTransactionCandidate.__table__], checkfirst=True)
            logger.info(f"Created missing table {ParsedTransactionCandidate.__tablename__}")
    except Exception as e:
        logger.error(f"Error ensuring table {ParsedTransactionCandidate.__tablename__} exists: {e}")
    session = SessionLocal()

    try:
        email = session.query(EmailRaw).filter(EmailRaw.id == email_id).first()
        if not email:
            logger.error(f"Email {email_id} not found for parsing")
            return
        logger.info(f"Parsing email {email_id} with subject: {email.subject}")
        plain_text = extract_plain_text(email.body)
        parsed = parse_email(email.subject, plain_text)

        row = ParsedTransactionCandidate(
            email_id=email.id,
            amount=parsed["amount"],
            currency=parsed["currency"],
            datetime_sgt=parsed["datetime_sgt"],
            inferred_sender=parsed["inferred_sender"],
            inferred_receiver=parsed["inferred_receiver"],
            debit_credit=parsed["debit_credit"],
            type_info=parsed["type_info"],
        )

        session.add(row)
        session.commit()
        
        # After session.commit() for ParsedTransactionCandidate:
        # EventBuilder().process_candidate(row.id)

        logger.info(f"Parsed email → ParsedTransactionCandidate {row.id}")

    except Exception as e:
        logger.error(f"Parser error: {e}")
        session.rollback()
        raise

    finally:
        session.close()