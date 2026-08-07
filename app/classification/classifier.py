from app.classification.rule_table import RULES
from app.parsing.account_alias_map import ACCOUNT_ALIAS_MAP
from app.core.config import settings

def normalize_party(party: str):
    """Normalize inferred sender/receiver to canonical name."""
    if not party:
        return None

    low = party.lower()

    for canonical, variants in ACCOUNT_ALIAS_MAP.items():
        for v in variants:
            if v.lower() in low:
                return canonical

    return "Other"


def _lookup_rule(sender, receiver):
    """Find the RULES entry matching this (sender, receiver) pair,
    case-insensitively. Returns None if no rule matches."""
    if not sender or not receiver:
        return None
    for rule in RULES:
        if rule["sender"].lower() == sender.lower() and rule["receiver"].lower() == receiver.lower():
            return rule
    return None


def classify(parsed: dict):
    """
    Determine the eventType + emailCountRequired using deterministic rules.
    """
    if settings.DEBUG:
        print(f"Classify input: {parsed}")
    inferred_sender = (parsed.get("inferred_sender"))
    inferred_receiver = (parsed.get("inferred_receiver"))
    debit_credit = parsed.get("debit_credit")  # debit, credit, spend, earn
    type_info = parsed.get("type_info")  # additional info from parser (eg "spend" if we are sure it's a spend)

    if settings.DEBUG:
        print(f"Classifying with: inferred_sender={inferred_sender}, inferred_receiver={inferred_receiver}, debit_credit={debit_credit}, type_info={type_info}")    

    # ---------------------------------------------------------------------
    # Step 1: deterministic (sender, receiver) lookup in RULES
    # ---------------------------------------------------------------------
    rule = _lookup_rule(inferred_sender, inferred_receiver)
    if rule:
        return {
            "eventType": rule["eventType"],
            "sender": inferred_sender,
            "receiver": inferred_receiver,
            "emailCountRequired": rule["emailCountRequired"],
        }

    # ---------------------------------------------------------------------
    # Step 2: fallback 1-email Spend/Earn determination from debit_credit
    # ---------------------------------------------------------------------
    if debit_credit in ("debit", "spend") and type_info == "spend":
        return {
            "eventType": "Spend",
            "sender": inferred_sender,
            "receiver": inferred_receiver,
            "emailCountRequired": 1,
        }

    if debit_credit in ("credit", "earn") and type_info == "earn":
        # Earn → income into your account (eg DBS account)
        return {
            "eventType": "Earn",
            "sender": inferred_sender,
            "receiver": inferred_receiver,
            "emailCountRequired": 1,
        }
    if type_info == "InternalTransfer":
        # InternalTransfer → money out of one account (eg ACB Online) into another account you own (eg DBS)
        return {
            "eventType": "InternalTransfer",
            "sender": inferred_sender,
            "receiver": inferred_receiver,
            "emailCountRequired": 2,
        }

    # ---------------------------------------------------------------------
    # Step 3: no rule matched - never return None (callers index into the
    # result dict); report "Unknown" so the caller can log/skip cleanly.
    # ---------------------------------------------------------------------
    return {
        "eventType": "Unknown",
        "sender": inferred_sender,
        "receiver": inferred_receiver,
        "emailCountRequired": None,
    }