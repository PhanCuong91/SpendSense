from types import SimpleNamespace

from app.misa.query import classify


def _row(inferred_sender, inferred_receiver):
    return SimpleNamespace(
        inferred_sender=inferred_sender, inferred_receiver=inferred_receiver
    )


def test_spend_when_sender_known_and_receiver_other():
    row = _row("PayLah", "Other")
    assert classify(row) == "Spend"


def test_earn_when_sender_other_and_receiver_known():
    row = _row("Other", "DBS")
    assert classify(row) == "Earn"


def test_excluded_when_both_other():
    row = _row("Other", "Other")
    assert classify(row) is None


def test_excluded_when_both_other_and_none():
    row = _row(None, None)
    assert classify(row) is None


def test_excluded_when_neither_other_internal_transfer():
    row = _row("DBS", "Trust")
    assert classify(row) is None
