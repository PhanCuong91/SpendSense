"""Map `parsed_transaction_candidate` rows to `MisaTransaction` objects.

See ai/update_misa_implementation/update_misa_design.md §4.2 for the field
mapping table this module implements.
"""

from datetime import datetime
from decimal import Decimal
from typing import Union

from app.db.models.parsed_candidate import ParsedTransactionCandidate
from app.misa.models import MisaTransaction
from app.misa.query import Classification

CATEGORY = "Bar & Coffee"


def format_datetime(dt: datetime) -> str:
    """Format a candidate's `datetime_sgt` for MISA's date field.

    Placeholder ISO 8601 format pending confirmation of the real format
    MISA's form expects (requirements.md §10.2 / design.md §7.3). Isolated
    here so it is a one-line change once that is confirmed.
    """
    return dt.isoformat()


def to_misa_transaction(
    row: ParsedTransactionCandidate, classification: Classification
) -> MisaTransaction:
    """Map a candidate row + its classification to a `MisaTransaction`.

    Per design.md §4.2:
      - amount: direct copy of `row.amount`.
      - account: `inferred_sender` for Spend, `inferred_receiver` for Earn.
      - datetime: `row.datetime_sgt`, formatted via `format_datetime()`.
      - category: fixed constant `"Bar & Coffee"`.
    """
    if classification == "Spend":
        account = row.inferred_sender
    elif classification == "Earn":
        account = row.inferred_receiver
    else:
        raise ValueError(f"Unsupported classification: {classification!r}")

    amount: Union[float, Decimal] = row.amount
    if isinstance(amount, Decimal):
        amount = float(amount)

    return MisaTransaction(
        amount=amount,
        account=account,
        datetime=format_datetime(row.datetime_sgt),
        category=CATEGORY,
    )
