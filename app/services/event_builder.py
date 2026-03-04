from datetime import datetime
from typing import Optional
from app.db.session import SessionLocal
from app.db.models.event import Event
from app.db.models.parsed_candidate import ParsedTransactionCandidate
from app.db.models.error_log import ErrorLog
from app.db.models.audit_log import AuditLog
from app.classification.classifier import classify
from app.core.logging import get_logger

logger = get_logger(__name__)


class EventBuilder:
    """
    Builds final Event objects from ParsedTransactionCandidates.
    Handles ONLY 1-email events (Spend, Earn, InternalTransfer with emailCountRequired=1).
    2-email events are handled by the correlator worker.
    """

    def __init__(self):
        self.session = SessionLocal()

    # -------------------------------------------------------
    # Public API
    # -------------------------------------------------------
    def process_candidate(self, candidate_id) -> Optional[Event]:
        """
        Main entrypoint.
        Attempt to create a 1-email Event from a parsed candidate.
        If classification requires 2 emails → ignore for correlator.
        """

        try:
            candidate = (
                self.session.query(ParsedTransactionCandidate)
                .filter(ParsedTransactionCandidate.id == candidate_id)
                .first()
            )
            if not candidate:
                logger.error(f"EventBuilder: Candidate not found {candidate_id}")
                return None

            cls = classify({
                "inferred_sender": candidate.inferred_sender,
                "inferred_receiver": candidate.inferred_receiver,
                "debit_credit": candidate.debit_credit,
            })

            event_type = cls["eventType"]
            sender = cls["sender"]
            receiver = cls["receiver"]
            emailCountRequired = cls["emailCountRequired"]

            # -------------------------------------------------------
            # Skip 2-email transfers → Correlator handles later
            # -------------------------------------------------------
            if emailCountRequired == 2:
                logger.info(
                    f"EventBuilder: Candidate {candidate_id} is part of a 2-email event ({event_type})."
                )
                return None

            # -------------------------------------------------------
            # Build 1-email Event
            # -------------------------------------------------------
            event = Event(
                event_type=event_type,
                sender=sender,
                receiver=receiver,
                amount=candidate.amount,
                currency=candidate.currency,
                datetime_sgt=candidate.datetime_sgt,
                raw_email_ids=[str(candidate.email_id)],
                description=f"1-email event of type {event_type}",
            )

            self.session.add(event)
            self.session.commit()

            self._audit(
                f"Created 1-email event of type {event_type}",
                target_id=event.id,
                metadata={"candidate_id": str(candidate_id)},
            )

            logger.info(f"EventBuilder: Created 1-email Event {event.id}")

            return event

        except Exception as e:
            self._log_error(candidate_id, e)
            logger.error(f"EventBuilder: Error building event: {e}")
            self.session.rollback()
            return None

        finally:
            self.session.close()

    # -------------------------------------------------------
    # Helpers
    # -------------------------------------------------------
    def _audit(self, action, target_id=None, metadata=None):
        audit = AuditLog(action=action, target_id=target_id, metadata=metadata)
        self.session.add(audit)
        self.session.commit()

    def _log_error(self, candidate_id, exception):
        err = ErrorLog(
            email_id=candidate_id,
            error_type="EventBuilderError",
            stack=str(exception),
        )
        self.session.add(err)
        self.session.commit()