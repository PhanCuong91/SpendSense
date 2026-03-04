'''
🎯 Behaviour Summary
✔ Checks amount equality
Exact match (amount_debit == amount_credit).
✔ Timestamp proximity
Uses:
abs(dt_debit - dt_credit) ≤ CORRELATION_WINDOW_MINUTES

Default = 15 minutes.
✔ Sender/Receiver assignment
Event inherits:

sender = debit.inferred_sender
receiver = credit.inferred_receiver

✔ Reference soft‑match
Similarity scoring:

Exact: 1.0
Substring: 0.7
Else: 0.0

✔ Greedy conflict resolution
Matches sorted by score descending so the best pairs are chosen first.
✔ Produces:

Event
CorrelationLink (bidirectional record)

✔ Avoids duplicate pairing
Using sets: used_debits, used_credits.


Next up, if you want:
🔹 Option E — Complete end‑to‑end runnable system
🔹 Full classifier logic
🔹 Integration tests for parser/classifier/correlator
🔹 Prometheus metrics for correlation
'''
from datetime import timedelta
from app.db.session import SessionLocal
from app.db.models.event import Event
from app.db.models.correlation_link import CorrelationLink
from app.db.models.parsed_candidate import (
    ParsedTransactionCandidate,
    DebitCredit,
)
from app.correlation.state_machine import PendingStore
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _time_diff_minutes(t1, t2):
    return abs((t1 - t2).total_seconds()) / 60.0


def _reference_similarity(ref1, ref2):
    """
    A simple similarity measure:
    - exact match: 1.0
    - one contains the other: 0.7
    - else: 0
    """
    if not ref1 or not ref2:
        return 0.0

    if ref1 == ref2:
        return 1.0

    if ref1 in ref2 or ref2 in ref1:
        return 0.7

    return 0.0


def _candidate_match_score(debit, credit):
    """
    Compute match score = weighted combination:
    - amount match (required)
    - timestamp closeness
    - reference similarity
    """
    score = 0.0

    # Amount must match exactly
    if debit.amount != credit.amount:
        return -1

    # Timestamp proximity (max window 15 min)
    diff_minutes = _time_diff_minutes(debit.datetime_sgt, credit.datetime_sgt)
    if diff_minutes > settings.CORRELATION_WINDOW_MINUTES:
        return -1

    # Increases match score for closeness
    score += max(0, (settings.CORRELATION_WINDOW_MINUTES - diff_minutes) / 10)

    # Reference similarity
    ref_sim = _reference_similarity(
        debit.raw_reference,
        credit.raw_reference,
    )
    score += ref_sim

    return score


def correlate_once():
    """
    One correlation cycle:
    - Fetch pending debit & credit candidates
    - Try to match them pairwise
    - Produce Event records
    """

    session = SessionLocal()

    try:
        debits = PendingStore.get_pending(session, DebitCredit.debit)
        credits = PendingStore.get_pending(session, DebitCredit.credit)

        if not debits or not credits:
            logger.info("Correlator: nothing to match.")
            return

        logger.info(f"Correlator: pending debits={len(debits)}, credits={len(credits)}")

        # Attempt all pairings
        matches = []
        for d in debits:
            best_match = None
            best_score = -1

            for c in credits:
                score = _candidate_match_score(d, c)
                if score > best_score:
                    best_score = score
                    best_match = c

            if best_score >= 0:
                matches.append((d, best_match, best_score))

        # Deduplicate: ensure each candidate only used once
        used_debits = set()
        used_credits = set()
        final_pairs = []

        # Sort by score descending (greedy optimal matching)
        matches.sort(key=lambda x: x[2], reverse=True)

        for d, c, score in matches:
            if d.id in used_debits or c.id in used_credits:
                continue
            used_debits.add(d.id)
            used_credits.add(c.id)
            final_pairs.append((d, c))

        if not final_pairs:
            logger.info("Correlator: no successful matches.")
            return

        for debit, credit in final_pairs:
            event = Event(
                event_type="InternalTransfer",
                sender=debit.inferred_sender,
                receiver=credit.inferred_receiver,
                amount=debit.amount,
                currency=debit.currency or credit.currency,
                datetime_sgt=debit.datetime_sgt,
                raw_email_ids=[str(debit.email_id), str(credit.email_id)],
                description=f"Matched debit {debit.id} + credit {credit.id}",
            )
            session.add(event)
            session.commit()

            link = CorrelationLink(
                debit_candidate_id=debit.id,
                credit_candidate_id=credit.id,
                event_id=event.id,
            )
            session.add(link)
            session.commit()

            logger.info(
                f"Correlator: created Event {event.id} from {debit.id}+{credit.id}"
            )

    except Exception as e:
        logger.error(f"Correlation error: {e}")
        session.rollback()
        raise

    finally:
        session.close()