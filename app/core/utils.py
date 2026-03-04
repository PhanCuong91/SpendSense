import re
from datetime import datetime
from app.core.timezone import to_sgt


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def safe_decimal(value):
    """Convert to Decimal, return None on failure."""
    from decimal import Decimal, InvalidOperation
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def format_datetime(dt: datetime):
    if not dt:
        return None
    return to_sgt(dt).isoformat()