from datetime import timedelta
from app.core.config import settings
from app.db.session import SessionLocal
from app.db.models.parsed_candidate import ParsedTransactionCandidate, DebitCredit


class PendingStore:
    """
    Utility class to fetch unmatched debit/credit candidates.
    """

    @staticmethod
    def get_pending(session, debit_credit_type: DebitCredit, recent_minutes=60):
        """
        Returns parsed candidates that are NOT already referenced by a CorrelationLink
        and fall within a recent time window.
        """
        from app.db.models.correlation_link import CorrelationLink

        cutoff = None
        if recent_minutes:
            from datetime import datetime, timezone
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=recent_minutes)

        query = session.query(ParsedTransactionCandidate).filter(
            ParsedTransactionCandidate.debit_credit == debit_credit_type
        ).outerjoin(
            CorrelationLink,
            (ParsedTransactionCandidate.id == CorrelationLink.debit_candidate_id) |
            (ParsedTransactionCandidate.id == CorrelationLink.credit_candidate_id)
        ).filter(CorrelationLink.id.is_(None))

        if cutoff:
            query = query.filter(
                ParsedTransactionCandidate.datetime_sgt >= cutoff
            )

        return query.all()