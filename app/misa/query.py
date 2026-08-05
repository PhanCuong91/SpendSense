"""Query and classify `parsed_transaction_candidate` rows for MISA export.

See ai/update_misa_implementation/update_misa_requirements.md §2.1 for the
classification rules implemented here.
"""

from datetime import date
from typing import List, Literal, Optional, Tuple

from sqlalchemy.orm import Session

from app.db.models.parsed_candidate import ParsedTransactionCandidate

Classification = Literal["Spend", "Earn"]

_OTHER = "Other"


def classify(row: ParsedTransactionCandidate) -> Optional[Classification]:
    """Classify a candidate row as "Spend", "Earn", or None (excluded).

    Uses only `inferred_sender` / `inferred_receiver` compared against the
    literal string "Other" — `debit_credit` and `type_info` are intentionally
    not used:
      - Spend: inferred_sender != "Other" and inferred_receiver == "Other".
      - Earn:  inferred_sender == "Other" and inferred_receiver != "Other".
      - Otherwise (both "Other"/unparsed, or neither "Other"/internal
        transfer legs) -> None, excluded.
    """
    is_sender_other = row.inferred_sender == _OTHER
    is_receiver_other = row.inferred_receiver == _OTHER

    if not is_sender_other and is_receiver_other:
        return "Spend"
    if is_sender_other and not is_receiver_other:
        return "Earn"
    return None


def get_candidates(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[ParsedTransactionCandidate]:
    """Query `parsed_transaction_candidate` rows, optionally filtered by an
    inclusive `datetime_sgt` range."""
    query = db.query(ParsedTransactionCandidate)
    if start_date is not None:
        query = query.filter(ParsedTransactionCandidate.datetime_sgt >= start_date)
    if end_date is not None:
        query = query.filter(ParsedTransactionCandidate.datetime_sgt <= end_date)
    return query.all()


def get_classified_candidates(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[Tuple[ParsedTransactionCandidate, Classification]]:
    """Query candidates and return only those classified as Spend or Earn,
    paired with their classification."""
    rows = get_candidates(db, start_date=start_date, end_date=end_date)
    classified = []
    for row in rows:
        classification = classify(row)
        if classification is not None:
            classified.append((row, classification))
    return classified
