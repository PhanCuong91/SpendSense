import re

# ---------------------------------------------------------
# AMOUNT PATTERNS (from SGD/VND examples)
# ---------------------------------------------------------
AMOUNT_REGEX = re.compile(
    r"""
    (?P<currency>SGD|VND)?          # Optional currency
    \s*\$?\s*                       # Optional $
    (?P<amount>[+-]?
        \d{1,3}
        (?:,\d{3})*
        (?:\.\d{2})?
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

# ---------------------------------------------------------
# DATE PATTERNS (from "02 Mar 23:08 (SGT)", "02 Mar 2026 23:08 SGT", "030326-11:54:07")
# ---------------------------------------------------------
DATE_PATTERNS = [
    re.compile(r"(?P<day>\d{2})\s(?P<mon>\w{3})\s(?P<hour>\d{2}):(?P<min>\d{2})"),
    re.compile(
        r"(?P<day>\d{2})\s(?P<mon>\w{3})\s(?P<year>\d{4})\s(?P<hour>\d{2}):(?P<min>\d{2})"
    ),
    re.compile(
        r"(?P<dd>\d{2})(?P<mm>\d{2})(?P<yy>\d{2})-(?P<hh>\d{2}):(?P<mi>\d{2}):(?P<ss>\d{2})"
    ),
]

# ---------------------------------------------------------
# SENDER/RECEIVER LINES
# ---------------------------------------------------------
FROM_LINE = re.compile(r"From:\s*(.*)", re.IGNORECASE)
TO_LINE = re.compile(r"To:\s*(.*)", re.IGNORECASE)

# ---------------------------------------------------------
# REFERENCE PATTERN (alphanumeric blocks 8–20 chars)
# ---------------------------------------------------------
REFERENCE_REGEX = re.compile(r"([A-Z0-9]{8,20})")

# ---------------------------------------------------------
# KEYWORD TRIGGERS
# ---------------------------------------------------------
DEBIT_KEYWORDS = [
    "you've spent",
    "debit -",
    "top-up",
    "scan & pay",
    "latest transaction: debit",
    "transfer from",
]

CREDIT_KEYWORDS = [
    "you've received",
    "received",
    "credit +",
    "latest transaction: credit",
]