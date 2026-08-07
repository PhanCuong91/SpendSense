from datetime import datetime
from app.correlation.correlator import _candidate_match_score
from app.db.models.parsed_candidate import ParsedTransactionCandidate


def make_candidate(amount, dt, sender=None, receiver=None, dc=None):
    c = ParsedTransactionCandidate(
        amount=amount,
        datetime_sgt=dt,
        inferred_sender=sender,
        inferred_receiver=receiver,
        debit_credit=dc,
    )
    return c


def test_candidate_match_score():
    d = make_candidate(
        amount=50.00,
        dt=datetime(2026, 3, 2, 23, 8),
    )
    c = make_candidate(
        amount=50.00,
        dt=datetime(2026, 3, 2, 23, 10),
    )
    score = _candidate_match_score(d, c)
    assert score > 0