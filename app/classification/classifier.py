from app.classification.rule_table import RULES
from app.parsing.account_alias_map import ACCOUNT_ALIAS_MAP


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


def classify(parsed: dict):
    """
    Determine the eventType + emailCountRequired using deterministic rules.
    """

    inferred_sender = normalize_party(parsed.get("inferred_sender"))
    inferred_receiver = normalize_party(parsed.get("inferred_receiver"))
    debit_credit = parsed.get("debit_credit")  # debit, credit, spend, earn

    # ---------------------------------------------------------------------
    # Step 1: 1-email Spend/Earn determination from debit_credit
    # ---------------------------------------------------------------------
    if debit_credit in ("spend", "debit"):
        return {
            "eventType": "Spend",
            "sender": inferred_sender,
            "receiver": inferred_receiver,
            "emailCountRequired": 1,
        }

    if debit_credit in ("earn", "credit"):
        # Earn → income into your account (eg DBS account)
        return {
            "eventType": "Earn",
            "sender": inferred_sender,
            "receiver": inferred_receiver,
            "emailCountRequired": 1,
        }

    # ---------------------------------------------------------------------
    # Step 2: Match deterministic rules (2-email InternalTransfer cases)
    # ---------------------------------------------------------------------
    for rule in RULES:
        if (
            inferred_sender and inferred_receiver and
            rule["sender"].lower() == inferred_sender.lower()
            and rule["receiver"].lower() == inferred_receiver.lower()
        ):
            return {
                "eventType": rule["eventType"],
                "sender": inferred_sender,
                "receiver": inferred_receiver,
                "emailCountRequired": rule["emailCountRequired"],
            }

    # ---------------------------------------------------------------------
    # Step 3: Fallback classification
    # ---------------------------------------------------------------------
    # If ambiguous: treat debit as Spend, credit as Earn
    if debit_credit == "debit":
        return {
            "eventType": "Spend",
            "sender": inferred_sender,
            "receiver": inferred_receiver,
            "emailCountRequired": 1,
        }

    if debit_credit == "credit":
        return {
            "eventType": "Earn",
            "sender": inferred_sender,
            "receiver": inferred_receiver,
            "emailCountRequired": 1,
        }

    # Completely unknown → bucket to Spend (safe fallback)
    return {
        "eventType": "Spend",
        "sender": inferred_sender,
        "receiver": inferred_receiver,
        "emailCountRequired": 1,
    }