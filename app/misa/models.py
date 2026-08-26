from dataclasses import dataclass
from typing import Literal, Optional

Classification = Literal["Spend", "Earn"]


@dataclass
class MisaTransaction:
    """A single Spend/Earn transaction ready to be entered into MISA Money Keeper.

    See ai/update_misa_implementation/update_misa_requirements.md §2.2 for the
    field mapping rules that produce these values.
    """

    amount: float
    account: str
    datetime: str
    category: str
    classification: Classification


@dataclass
class MisaImportResult:
    """The outcome of attempting to import one MisaTransaction into MISA."""

    success: bool
    error_message: Optional[str] = None
