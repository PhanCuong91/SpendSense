import re
from datetime import datetime
from dateutil import tz

SGT = tz.gettz("Asia/Singapore")

def normalize_whitespace(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_amount_str(amount_str: str) -> float:
    cleaned = amount_str.replace(",", "")
    return float(cleaned)


def normalize_date(match: dict):
    """
    Handles all three date patterns found in examples.
    Converts into timezone-aware datetime (SGT).
    """
    mon_map = {
        "Jan": 1,
        "Feb": 2,
        "Mar": 3,
        "Apr": 4,
        "May": 5,
        "Jun": 6,
        "Jul": 7,
        "Aug": 8,
        "Sep": 9,
        "Oct": 10,
        "Nov": 11,
        "Dec": 12,
    }

    # Pattern 1: 02 Mar 23:08
    if "day" in match and "mon" in match and "hour" in match:
        return datetime(
            year=datetime.now().year,
            month=mon_map[match["mon"]],
            day=int(match["day"]),
            hour=int(match["hour"]),
            minute=int(match["min"]),
            tzinfo=SGT,
        )

    # Pattern 2: 02 Mar 2026 23:08
    if "year" in match:
        return datetime(
            year=int(match["year"]),
            month=mon_map[match["mon"]],
            day=int(match["day"]),
            hour=int(match["hour"]),
            minute=int(match["min"]),
            tzinfo=SGT,
        )

    # Pattern 3: 030326-11:54:07
    if "dd" in match:
        return datetime(
            year=int("20" + match["yy"]),
            month=int(match["mm"]),
            day=int(match["dd"]),
            hour=int(match["hh"]),
            minute=int(match["mi"]),
            second=int(match["ss"]),
            tzinfo=SGT,
        )

    return None