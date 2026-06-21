'''
🎉 Option C completed — You now have a full parser engine.
This parser:

Correctly extracts amounts, currencies, dates, senders, receivers, reference numbers, direction (debit/credit/spend/earn).
Supports all formats in your training data.
Normalizes everything to clean, strongly typed data.
Produces a ParsedTransactionCandidate that plugs directly into your classifier and correlator.
'''

from email.mime import text
import re
from app.parsing.regex_patterns import (
    AMOUNT_REGEX_SGD,
    AMOUNT_REGEX_VND,
    DATE_PATTERNS,
    DATE_PATTERNS_DBS_2_PAYLAH,
    FROM_LINE,
    TO_LINE,
    REFERENCE_REGEX,
    DEBIT_KEYWORDS,
    CREDIT_KEYWORDS,
    TRUST_RECEIVED,
    TRUST_SPENT
)
from app.parsing.account_alias_map import ACCOUNT_ALIAS_MAP
from app.parsing.normalization import (
    normalize_amount_str,
    normalize_date,
    normalize_whitespace,
)
from app.core.config import settings
from app.core.logging import get_logger, save_to_file
logger = get_logger(__name__)

# 0. Clean up html entities, newlines, extra spaces early for easier regex parsing just keep the content the same

from bs4 import BeautifulSoup

def extract_plain_text(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    # Get all visible text, ignoring tags like tr, td, table, style, script, etc.
    return soup.get_text(separator="\n", strip=True)



# ---------------------------------------------------------
# 1. Extract Amount
# ---------------------------------------------------------
def extract_amount(text: str):
    if 'SGD' in text.upper():
        m = AMOUNT_REGEX_SGD.search(text)
        currency = (m.group("currency") or "SGD").upper()
        sign = None
    elif 'VND' in text.upper():
        if settings.DEBUG:
            print("Extracting VND amount...")
        m = AMOUNT_REGEX_VND.findall(text)
        if len(m) >= 2:
            if settings.DEBUG:
                print(f"Multiple VND amounts found: {m}. Taking the last one.")
            m = m[-1]  # take the last match if multiple
            currency = m[2].upper() if m else "VND"
            sign = m[0] if m else None
        else:
            if settings.DEBUG:
                print("No VND amount found in text with VND keyword.")
            logger.warning("No VND amount found in text with VND keyword.")
            m = None
    else:
        m = None

    if not m:
        return None, None, None

    
    if currency == "VND":
        amount = normalize_amount_str(m[1]) # amount group in VND regex
        pass
    elif currency == "SGD":
        amount = normalize_amount_str(m.group("amount"))
    else:
        amount = None
        logger.warning(f"Unrecognized currency: {currency}")
        
    return currency, amount, sign


# ---------------------------------------------------------
# 2. Extract Date
# ---------------------------------------------------------
def extract_date(inferred_sender, inferred_receiver,  text: str):
    if inferred_sender == "DBS" and inferred_receiver == "PayLah":
        if settings.DEBUG:
            print("Applying DBS->PayLah specific date extraction...")
        for pattern in DATE_PATTERNS_DBS_2_PAYLAH:
            m = pattern.search(text)
            if m:
                if settings.DEBUG:
                    print(f"DBS->PayLah date pattern matched: {pattern.pattern} → {m.groupdict()}")
                return normalize_date(m.groupdict())
        if settings.DEBUG:
            print("No date match found for DBS->PayLah specific patterns. Falling back to general patterns.")
        return None
    for pattern in DATE_PATTERNS:
        m = pattern.search(text)
        if not m:
            if settings.DEBUG:
                print(f"No match for date pattern: {pattern.pattern}")
            continue
        # if 'yyyy' not in m.groupdict() and 'yy' not in m.groupdict():
        #     print(f"Date pattern matched but no year found: {pattern.pattern} → {m.groupdict()}. Skipping this match.")
        #     continue
        if settings.DEBUG:
            print(f"Date pattern matched: {pattern.pattern} → {m.groupdict()}")
        return normalize_date(m.groupdict())
    return None


# ---------------------------------------------------------
# 3. Extract Sender / Receiver from lines
# ---------------------------------------------------------
def extract_from_and_to_for_DBS_and_PayLah(body: str):
    inferred_sender = 'Other'
    inferred_receiver = 'Other'

    # From:
    fm = FROM_LINE.search(body)
    if settings.DEBUG:
        print(f"Searching for 'From:' line in email body. Match found: {bool(fm)}")
    if fm:
        if settings.DEBUG:
            print(f"Found 'From:' line: {fm.group(0)}")
        inferred_sender = fm.group(1).strip()
        if settings.DEBUG:
            print(f"Extracted sender from 'From:' line: {inferred_sender}")

    # To:
    tm = TO_LINE.search(body)
    if tm:
        inferred_receiver = tm.group(1).strip()

    return inferred_sender, inferred_receiver

def extract_from_and_to_for_trust(text: str):
    # Look for "From: XYZ" anywhere in the text
    fm = TRUST_SPENT.search(text)
    inferred_sender = "Other"
    inferred_receiver = "Other"
    if fm:
        inferred_sender = fm.group(1).strip()
    tm = TRUST_RECEIVED.search(text)
    if tm:       
        inferred_receiver = tm.group(1).strip()
    if inferred_sender == "Other":
        if "You've received a PayNow transfer" in text:
            inferred_sender = "DBS" # common case where sender is DBS but not explicitly stated
    if inferred_receiver == "Other":
        if settings.DEBUG:
            print("No explicit receiver found for Trust transaction. Checking for '(ending 014U)' pattern to infer receiver...")
        if "(ending 014)" in text:
            if settings.DEBUG:
                print("Detected '(ending 014U)' in text, inferring receiver as Trust")
            inferred_receiver = "Trust" # common case where receiver is Trust but not explicitly stated
    return inferred_sender, inferred_receiver

def extract_from_and_to_for_ACB(text: str):
    if "ACB" in text:
        if settings.DEBUG:
            print("Extracting parties for ACB...")
        if "debit" in text.lower():
            if "6422417" in text.lower():
                return "ACB Online", "Other"
            else:
                return "ACB", "Other"
        elif "credit" in text.lower():
            if "6422417" in text.lower():
                if "FINFAN" in text:
                    return "DBS", "ACB Online"
                else:
                    return "Other", "ACB Online"
            else:
                return "Other", "ACB"
    return "Other", "Other"
def extract_parties(body: str):
    inferred_sender = 'Other'
    inferred_receiver = 'Other'
    inferred_sender, inferred_receiver = extract_from_and_to_for_DBS_and_PayLah(body)
    if inferred_sender == "Other" and inferred_receiver == "Other":
        inferred_sender, inferred_receiver = extract_from_and_to_for_trust(body)
    if inferred_sender == "Other" and inferred_receiver == "Other":
        inferred_sender, inferred_receiver = extract_from_and_to_for_ACB(body)

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
                if settings.DEBUG:
                    print(f"Mapping raw name '{raw_name}' to canonical account '{canonical}' using variant '{v}'")
                return canonical
    return 'Other'  # fallback


# ---------------------------------------------------------
# 5. Determine debit/credit direction
# ---------------------------------------------------------
def detect_debit_credit(inferred_sender: str, inferred_receiver: str, text: str = ""):
    debit_credit = None
    if inferred_sender != "Other" and inferred_receiver == "Other":
        debit_credit = "debit"
    elif inferred_sender == "Other" and inferred_receiver != "Other":
        debit_credit = "credit"
    elif inferred_sender == "DBS" and (inferred_receiver == "PayLah" or inferred_receiver == "Trust" or inferred_receiver == "ACB Online" or inferred_receiver == "ACB"):
        if email_sender(text) == "DBS":
            debit_credit = "debit"  # default to debit for transfers between known accounts
        else:
            debit_credit = "credit"  # if sender is DBS but text doesn't match known DBS patterns, treat as credit (e.g. refund)
    return debit_credit

def dectect_type(inferred_sender: str, inferred_receiver: str, text: str):
    if settings.DEBUG:
        print(f"Detecting type with inferred_sender='{inferred_sender}', inferred_receiver='{inferred_receiver}'")
    t = None
    if inferred_sender != "Other" and inferred_receiver != 'Other':
        return "InternalTransfer"
    elif inferred_sender != "Other" and inferred_receiver == "Other":
        t = "spend"
    elif inferred_sender == "Other" and inferred_receiver != "Other":
        t = "earn"
    if t == "spend" and inferred_sender == "DBS":
        if "(NRIC ending 014U)" in text or "WESTERN UNION" in text or "You’ve successfully top-up to your PayLah!" in text:
            t = "InternalTransfer"
    elif t == "spend" and inferred_sender == "ACB Online":
        # if "Debit -" in text and "IB PHAN CUONG CHUYEN KHOAN" in text:
        if "Debit -" in text:
            t = "InternalTransfer"
    if t == "earn":
        if inferred_receiver == "Trust":
            if "You've received a PayNow transfer" in text:
                t = "InternalTransfer"
        elif inferred_receiver == "ACB Online":
            if "FINFAN" in text:
                t = "InternalTransfer"
        elif inferred_receiver == "ACB":
            if "Credit +" in text:
                t = "InternalTransfer"
    return t

# ---------------------------------------------------------
# 6. Extract alphanumeric reference
# ---------------------------------------------------------
def extract_reference(text: str):
    m = REFERENCE_REGEX.search(text)
    return m.group(1) if m else None

def email_sender(text: str):
    if "DBS" in text:
        return "DBS"
    elif "PayLah" in text:
        return "PayLah"
    elif "Trust" in text:
        return "Trust"
    elif "ACB Online" in text:
        return "ACB Online"
    elif "ACB" in text:
        return "ACB"
    else:
        return "Other"
# ---------------------------------------------------------
# 7. Main Parser
# ---------------------------------------------------------
def parse_email(subject: str, body: str):
    # Normalize whitespace early
    subject = normalize_whitespace(subject or "")
    body = normalize_whitespace(body or "")

    # Combine for parsing convenience
    text = subject + " " + body
    logger.info(f"Parsing email with combined text length: {(text)}")

    # Amount
    currency, amount, sign = extract_amount(text)

    # Date
    

    # Sender/Receiver raw extraction
    raw_sender, raw_receiver = extract_parties(body)
    if settings.DEBUG:
        print(f"Extracted from text - raw sender: {raw_sender}, raw receiver: {raw_receiver}")

    # Canonical mapping
    if raw_sender  in ['Other', 'PayLah', 'Trust', 'ACB Online', 'ACB', 'DBS']:
        logger.warning(f"Raw sender '{raw_sender}' not recognized in known accounts. Defaulting to 'Other'.")
        inferred_sender = raw_sender
    else:
        inferred_sender = map_account_alias(raw_sender)
    if raw_receiver in ['Other', 'PayLah', 'Trust', 'ACB Online', 'ACB', 'DBS']:
        inferred_receiver = raw_receiver
    else:
        inferred_receiver = map_account_alias(raw_receiver)
    if settings.DEBUG:
        print(f"Extracted from text - inferred sender: {inferred_sender}, inferred receiver: {inferred_receiver}")

    # Debit/Credit flag
    debit_credit = detect_debit_credit(inferred_sender, inferred_receiver,text)

    type_info = dectect_type(inferred_sender, inferred_receiver, text)

    dt = extract_date(inferred_sender, inferred_receiver,text)
    if settings.DEBUG:
        print(f"Extracted date: {dt}")
    # Reference
    reference = extract_reference(text)

    return {
        "amount": amount,
        "currency": currency,
        "sign": sign,
        "datetime_sgt": dt,
        "inferred_sender": inferred_sender,
        "inferred_receiver": inferred_receiver,
        "debit_credit": debit_credit,
        "type_info": type_info,
    }
if __name__ == "__main__":
    # Quick test
    # Usage example:

    files = [
        "decoded_email_19cb5f58aac5afc1.json", 
        "decoded_email_19cb6f62952e4f89.json", 
        "decoded_email_19cb8ba57beb5378.json",
        "decoded_email_19cb8fb28b452b04.json", 
        "decoded_email_19cb8fcc291e89e6.json", "decoded_email_19cb70bd1b58ad9a.json", "decoded_email_19cb893c5f71c094.json", "decoded_email_19cb6759c2f7f46e.json", "decoded_email_19cbb294b644a5ac.json", "decoded_email_19cbba398c9a121c.json", "decoded_email_19cbc2b2f37a943f.json", "decoded_email_19cbc4eea067a7ca.json", "decoded_email_19cbd85dc5e02094.json", "decoded_email_19cbddac96d9a1ac.json", "decoded_email_19cbddb7083f3187.json", "decoded_email_19cbddd385f7274a.json", "decoded_email_19cbdedf2e7cbe1b.json", "decoded_email_19cc7aa1d483ed03.json", "decoded_email_19cc045ccb41fb50.json", "decoded_email_19cc152f3dec400f.json", "decoded_email_19cc286d65480e67.json", "decoded_email_19cc562cb1914635.json", "decoded_email_19cc6502c94c7696.json", "decoded_email_19cc8363c18b0fef.json"]
    sample_subject = "asdas"
    for file in files:

        with open(file, encoding="utf-8") as f:
            html = f.read()
        plain_text = extract_plain_text(html)
        print("--------------Start of Email--------------")
        print(f"---------------{file}-------------")
        # print(plain_text)
        print("\n\nExtracted Data:")
        extracted = parse_email(sample_subject, plain_text)
        print(extracted)
        print("--------------End of Email--------------")