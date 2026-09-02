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

CATEGORY = "Bars & Coffee"
EARN_CATEGORY = "Balance"

# Map canonical account names produced by the parser/query layer to the exact
# account names displayed in MISA's dropdown (case and diacritics matter there).
MISA_ACCOUNT_NAME_MAP = {
    "ACB": "ATM",
    "ACB Online": "Acb online",
    "DBS": "DBS bank",
    "PayLah": "Paylah",
    "Trust": "Ngân hàng Trust",
}


def to_misa_account_name(canonical_account: str) -> str:
    """Return the MISA account label for a canonical account name.

    Falls back to the canonical name unchanged when no mapping exists.
    """
    return MISA_ACCOUNT_NAME_MAP.get(canonical_account, canonical_account)


def format_datetime(dt: datetime) -> str:
    """Format a candidate's `datetime_sgt` for MISA's date field.

    MISA's Add Transaction popup expects `DD/MM/YYYY HH:MM` (confirmed via
    manual UI inspection; requirements.md §10.2 / design.md §7.3).
    """
    return dt.strftime("%d/%m/%Y %H:%M")


def to_misa_transaction(
    row: ParsedTransactionCandidate, classification: Classification
) -> MisaTransaction:
    """Map a candidate row + its classification to a `MisaTransaction`.

    Per design.md §4.2:
      - amount: direct copy of `row.amount`.
      - account: `inferred_sender` for Spend, `inferred_receiver` for Earn.
      - datetime: `row.datetime_sgt`, formatted via `format_datetime()`.
      - category: fixed constant `"Bars & Coffee"` for Spend, `"Balance"`
        for Earn (Spend and Earn have distinct category lists in MISA;
        `CATEGORY` is invalid for Earn rows and will be rejected by MISA's
        own validation).
    """
    if classification == "Spend":
        account = to_misa_account_name(row.inferred_sender)
        category = CATEGORY
    elif classification == "Earn":
        account = to_misa_account_name(row.inferred_receiver)
        category = EARN_CATEGORY
    else:
        raise ValueError(f"Unsupported classification: {classification!r}")

    amount: Union[float, Decimal] = row.amount
    if isinstance(amount, Decimal):
        amount = float(amount)

    return MisaTransaction(
        amount=amount,
        account=account,
        datetime=format_datetime(row.datetime_sgt),
        category=category,
        classification=classification,
    )
