from app.classification.classifier import classify


def test_dbs_to_trust():
    parsed = {
        "inferred_sender": "DBS",
        "inferred_receiver": "Trust",
        "debit_credit": None,
    }
    r = classify(parsed)
    assert r["eventType"] == "InternalTransfer"
    assert r["emailCountRequired"] == 2


def test_paylah_spend():
    parsed = {
        "inferred_sender": "PayLah",
        "inferred_receiver": "Other",
        "debit_credit": "spend",
    }
    r = classify(parsed)
    assert r["eventType"] == "Spend"
    assert r["emailCountRequired"] == 1


def test_dbs_earn():
    parsed = {
        "inferred_sender": "Other",
        "inferred_receiver": "DBS",
        "debit_credit": "earn",
    }
    r = classify(parsed)
    assert r["eventType"] == "Earn"
    assert r["emailCountRequired"] == 1