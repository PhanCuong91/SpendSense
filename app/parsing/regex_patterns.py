import re

# ---------------------------------------------------------
# AMOUNT PATTERNS (from SGD/VND examples)
# ---------------------------------------------------------
AMOUNT_REGEX_SGD = re.compile(
    r"(?P<currency>SGD)(?:\$)?\s?(?P<amount>\d{1,9}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)",
    re.VERBOSE | re.IGNORECASE,
)
AMOUNT_REGEX_VND = re.compile(
    r"(?P<sign>[+-])?(?P<amount>\d{1,9}(?:,\d{3})*(?:\.\d{1,2})?|\d+)(?:\s)?(?P<currency>VND)",
    re.VERBOSE | re.IGNORECASE,
)


# ---------------------------------------------------------
# DATE PATTERNS (from "02 Mar 23:08 (SGT)", "02 Mar 2026 23:08 SGT", "030326-11:54:07")
# ---------------------------------------------------------
DATE_PATTERNS = [
    re.compile(r"dated (?P<day>\d{1,2})\s(?P<mon>\w{3})"),
    re.compile(r"(?P<day>\d{1,2})\s(?P<mon>\d{1,2}|([A-Z][a-z]*))\s(?P<yyyy>\d{2,4}) "),
        re.compile(r"(?P<dd>\d{2})\/(?P<mm>\d{2})\/(?P<yy>\d{2,4})"), # ABC bank format like 03/03/2026
    re.compile(r"(?P<dd>\d{2})(?P<mm>\d{2})(?P<yy>\d{2})-"),
]
DATE_PATTERNS_DBS_2_PAYLAH = [
    re.compile(r"(?P<day>\d{2}) (?P<mon>\w{3})\d{2}:"),
]

# ---------------------------------------------------------
# SENDER/RECEIVER LINES
# ---------------------------------------------------------
FROM_LINE = re.compile(r"From:\s*(.*?)\s*To:", re.DOTALL)
TO_LINE = re.compile(r"To:\s*(.*)", re.IGNORECASE)
TRUST_SPENT = re.compile(r"You've spent\s*(.*)", re.IGNORECASE)
TRUST_RECEIVED = re.compile(r"You've received\s*(.*)", re.IGNORECASE)

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
    "ending 014u",
]

CREDIT_KEYWORDS = [
    "you've received",
    "received",
    "credit +",
    "latest transaction: credit",
    "Paynow transfer",
]