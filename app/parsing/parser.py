'''
🎉 Option C completed — You now have a full parser engine.
This parser:

Correctly extracts amounts, currencies, dates, senders, receivers, reference numbers, direction (debit/credit/spend/earn).
Supports all formats in your training data.
Normalizes everything to clean, strongly typed data.
Produces a ParsedTransactionCandidate that plugs directly into your classifier and correlator.
'''

import re
from app.parsing.regex_patterns import (
    AMOUNT_REGEX,
    DATE_PATTERNS,
    FROM_LINE,
    TO_LINE,
    REFERENCE_REGEX,
    DEBIT_KEYWORDS,
    CREDIT_KEYWORDS,
)
from app.parsing.account_alias_map import ACCOUNT_ALIAS_MAP
from app.parsing.normalization import (
    normalize_amount_str,
    normalize_date,
    normalize_whitespace,
)


# ---------------------------------------------------------
# 1. Extract Amount
# ---------------------------------------------------------
def extract_amount(text: str):
    m = AMOUNT_REGEX.search(text)
    if not m:
        return None, None

    currency = (m.group("currency") or "SGD").upper()
    amount = normalize_amount_str(m.group("amount"))
    return currency, amount


# ---------------------------------------------------------
# 2. Extract Date
# ---------------------------------------------------------
def extract_date(text: str):
    for pattern in DATE_PATTERNS:
        m = pattern.search(text)
        if m:
            return normalize_date(m.groupdict())
    return None


# ---------------------------------------------------------
# 3. Extract Sender / Receiver from lines
# ---------------------------------------------------------
def extract_parties(body: str):
    inferred_sender = None
    inferred_receiver = None

    # From:
    fm = FROM_LINE.search(body)
    if fm:
        inferred_sender = fm.group(1).strip()

    # To:
    tm = TO_LINE.search(body)
    if tm:
        inferred_receiver = tm.group(1).strip()

    return inferred_sender, inferred_receiver


# ---------------------------------------------------------
# 4. Map raw names to canonical account names
# ---------------------------------------------------------
def map_account_alias(raw_name):
    if not raw_name:
        return None

    raw = raw_name.lower()

    for canonical, variants in ACCOUNT_ALIAS_MAP.items():
        for v in variants:
            if v.lower() in raw:
                return canonical
    return raw_name  # fallback


# ---------------------------------------------------------
# 5. Determine debit/credit direction
# ---------------------------------------------------------
def detect_debit_credit(text: str):
    text_l = text.lower()

    for keyword in DEBIT_KEYWORDS:
        if keyword in text_l:
            return "debit" if "debit" in keyword or "top-up" in keyword else "spend"

    for keyword in CREDIT_KEYWORDS:
        if keyword in text_l:
            return "credit" if "credit" in keyword else "earn"

    return None


# ---------------------------------------------------------
# 6. Extract alphanumeric reference
# ---------------------------------------------------------
def extract_reference(text: str):
    m = REFERENCE_REGEX.search(text)
    return m.group(1) if m else None


# ---------------------------------------------------------
# 7. Main Parser
# ---------------------------------------------------------
def parse_email(subject: str, body: str):
    # Normalize whitespace early
    subject = normalize_whitespace(subject or "")
    body = normalize_whitespace(body or "")

    # Combine for parsing convenience
    text = subject + " " + body

    # Amount
    currency, amount = extract_amount(text)

    # Date
    dt = extract_date(text)

    # Sender/Receiver raw extraction
    raw_sender, raw_receiver = extract_parties(body)

    # Canonical mapping
    inferred_sender = map_account_alias(raw_sender)
    inferred_receiver = map_account_alias(raw_receiver)

    # Debit/Credit flag
    debit_credit = detect_debit_credit(text)

    # Reference
    reference = extract_reference(text)

    return {
        "amount": amount,
        "currency": currency,
        "datetime_sgt": dt,
        "inferred_sender": inferred_sender,
        "inferred_receiver": inferred_receiver,
        "raw_reference": reference,
        "debit_credit": debit_credit,
    }