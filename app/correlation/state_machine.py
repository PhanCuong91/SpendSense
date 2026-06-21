from datetime import timedelta
from app.core.config import settings
from app.db.session import SessionLocal
from app.db.models.parsed_candidate import ParsedTransactionCandidate, DebitCredit


class PendingStore:
    """
    Utility class to fetch unmatched debit/credit candidates.
    """

    @staticmethod
    def get_pending(session, debit_credit_type: DebitCredit, recent_dates=60):
        """ Retrieves a list of `ParsedTransactionCandidate` objects that:
        - Match the specified `debit_credit_type` and have a `type_info` of "InternalTransfer".
        - Are not already referenced by any `CorrelationLink` (i.e., not linked as debit or credit candidates).
        - Optionally, fall within a recent time window (default: last 60 minutes).
        Args:
            session: SQLAlchemy session used for querying the database.
            debit_credit_type (DebitCredit): The debit or credit type to filter candidates.
            recent_minutes (int, optional): The time window (in minutes) to filter candidates by their `datetime_sgt`. Defaults to 60.
        Returns:
            List[ParsedTransactionCandidate]: The filtered list of transaction candidates.
        Line-by-line explanation:
            - Imports `CorrelationLink` model for joining.
            - Calculates a cutoff datetime if `recent_minutes` is provided.
            - Builds a query to filter candidates by `debit_credit_type` and `type_info`.
            - Performs an outer join with `CorrelationLink` to find candidates not referenced in any link.
            - Filters out candidates already linked by checking `CorrelationLink.id` is `None`.
            - If a cutoff is set, further filters candidates to those within the recent time window.
            - Returns all matching candidates as a list.
        """
        """
        Returns parsed candidates that are NOT already referenced by a CorrelationLink
        and fall within a recent time window.
        """
        from app.db.models.correlation_link import CorrelationLink
        from app.db.models.event import Event  # Import your additional table

        cutoff = None
        if recent_dates:
            from datetime import datetime, timezone
            cutoff = datetime.now(timezone.utc) - timedelta(days=recent_dates)  # For testing, use a long window to capture all candidates
            

            query = session.query(ParsedTransactionCandidate
            ).filter(
                (ParsedTransactionCandidate.debit_credit == debit_credit_type) & (ParsedTransactionCandidate.type_info == "InternalTransfer")
            ).outerjoin(
                CorrelationLink,
                (ParsedTransactionCandidate.id == CorrelationLink.debit_candidate_id) |
                (ParsedTransactionCandidate.id == CorrelationLink.credit_candidate_id)
            ).filter(
                CorrelationLink.id.is_(None)
            )

        if cutoff:
            query = query.filter(
                ParsedTransactionCandidate.datetime_sgt >= cutoff
            )

        return query.all()