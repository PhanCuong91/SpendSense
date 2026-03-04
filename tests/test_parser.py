from app.parsing.parser import parse_email


def test_parse_spend_paylah():
    subject = "Transaction Alerts"
    body = """
    Dear Sir / Madam,
    We refer to your PayLah! Scan & Pay Transfer dated 03 Mar.
    Date & Time: 03 Mar 08:21 (SGT)
    Amount: SGD2.00
    From: PayLah! Wallet (Mobile ending 3162)
    To: VEGETARIAN PANCAKE
    """
    parsed = parse_email(subject, body)

    assert parsed["amount"] == 2.00
    assert parsed["currency"] == "SGD"
    assert parsed["inferred_sender"] == "DBS"   # PayLah alias
    assert parsed["debit_credit"] in ("debit", "spend")