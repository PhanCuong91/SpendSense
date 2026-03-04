# Deterministic rule table based on training data

RULES = [
    # 2-email internal transfers
    {
        "eventType": "InternalTransfer",
        "sender": "DBS",
        "receiver": "Trust",
        "emailCountRequired": 2,
    },
    {
        "eventType": "InternalTransfer",
        "sender": "DBS",
        "receiver": "ACB Online",
        "emailCountRequired": 2,
    },
    {
        "eventType": "InternalTransfer",
        "sender": "ACB Online",
        "receiver": "ACB",
        "emailCountRequired": 2,
    },

    # 1-email internal transfers
    {
        "eventType": "InternalTransfer",
        "sender": "DBS",
        "receiver": "Paylah",
        "emailCountRequired": 1,
    },

    # Spend events
    {
        "eventType": "Spend",
        "sender": "ACB Online",
        "receiver": "Other",
        "emailCountRequired": 1,
    },
    {
        "eventType": "Spend",
        "sender": "ACB",
        "receiver": "Other",
        "emailCountRequired": 1,
    },
    {
        "eventType": "Spend",
        "sender": "Trust",
        "receiver": "Other",
        "emailCountRequired": 1,
    },
    {
        "eventType": "Spend",
        "sender": "Paylah",
        "receiver": "Other",
        "emailCountRequired": 1,
    },

    # Earn events (incoming transfers)
    {
        "eventType": "Earn",
        "sender": "Other",
        "receiver": "DBS",
        "emailCountRequired": 1,
    },
]