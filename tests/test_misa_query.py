from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

from app.misa.mapper import CATEGORY, to_misa_transaction
from app.misa.query import classify


def _row(inferred_sender, inferred_receiver, amount=None, datetime_sgt=None):
    return SimpleNamespace(
        inferred_sender=inferred_sender,
        inferred_receiver=inferred_receiver,
        amount=amount,
        datetime_sgt=datetime_sgt,
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


def test_maps_spend_row_account_from_sender():
    dt = datetime(2026, 8, 5, 12, 30, 0)
    row = _row("PayLah", "Other", amount=Decimal("12.50"), datetime_sgt=dt)

    tx = to_misa_transaction(row, "Spend")

    assert tx.amount == 12.50
    assert tx.account == "PayLah"
    assert tx.datetime == dt.isoformat()
    assert tx.category == CATEGORY


def test_maps_earn_row_account_from_receiver():
    dt = datetime(2026, 8, 5, 9, 0, 0)
    row = _row("Other", "DBS", amount=Decimal("100.00"), datetime_sgt=dt)

    tx = to_misa_transaction(row, "Earn")

    assert tx.amount == 100.00
    assert tx.account == "DBS"
    assert tx.datetime == dt.isoformat()
    assert tx.category == CATEGORY
