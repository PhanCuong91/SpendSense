import pytest

from app.db.base import Base
from app.db.session import engine

# Import all models so Base.metadata knows the tables
from app.db.models import (  # noqa: F401
    EmailRaw,
    ParsedTransactionCandidate,
    Event,
    CorrelationLink,
    ErrorLog,
    AuditLog,
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create all tables before tests run, drop them afterwards."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
