from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models.email_raw import EmailRaw
from app.db.models.misa_import_state import MisaImportState
from app.db.models.parsed_candidate import ParsedTransactionCandidate
from app.misa.dedup_store import DedupStore


@pytest.fixture
def db_session():
    """Provide a function-scoped in-memory DB session for dedup-store tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _make_candidate(session, inferred_sender="PayLah", inferred_receiver="Other"):
    email = EmailRaw(
        gmail_message_id=f"test-{uuid4()}",
        internal_date=datetime.now(timezone.utc),
    )
    session.add(email)
    session.commit()

    candidate = ParsedTransactionCandidate(
        email_id=email.id,
        amount=Decimal("10.50"),
        currency="SGD",
        datetime_sgt=datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc),
        inferred_sender=inferred_sender,
        inferred_receiver=inferred_receiver,
    )
    session.add(candidate)
    session.commit()
    return candidate


def test_fresh_store_treats_all_ids_as_not_imported(db_session):
    candidate = _make_candidate(db_session)
    store = DedupStore(db=db_session)

    assert store.is_imported(candidate.id) is False
    assert store.is_imported(str(candidate.id)) is False


def test_mark_imported_persists_across_reload(db_session):
    candidate = _make_candidate(db_session)
    store = DedupStore(db=db_session)

    store.mark_imported(
        candidate.id,
        {"amount": "10.50", "account": "PayLah", "classification": "Spend"},
    )

    assert store.is_imported(candidate.id) is True

    # Simulate a fresh process using a new session on the same database.
    new_session = sessionmaker(bind=db_session.bind)()
    reloaded = DedupStore(db=new_session)
    assert reloaded.is_imported(candidate.id) is True

    # The stored metadata is also persisted.
    row = new_session.get(MisaImportState, candidate.id)
    assert row is not None
    assert row.status == "imported"
    assert row.account == "PayLah"
    assert row.classification == "Spend"


def test_failed_attempt_is_never_written_and_remains_eligible(db_session):
    candidate = _make_candidate(db_session)
    store = DedupStore(db=db_session)

    # A failed row simply never calls mark_imported(); nothing should be
    # written to the DB, and the id must remain eligible for retry.
    assert store.is_imported(candidate.id) is False

    new_session = sessionmaker(bind=db_session.bind)()
    reloaded = DedupStore(db=new_session)
    assert reloaded.is_imported(candidate.id) is False
