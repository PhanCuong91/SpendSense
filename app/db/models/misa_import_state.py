import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Numeric, String, TIMESTAMP, Uuid
from sqlalchemy.orm import relationship

from app.db.base import Base


class MisaImportState(Base):
    __tablename__ = "misa_import_state"

    parsed_candidate_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("parsed_transaction_candidate.id", ondelete="CASCADE"),
        primary_key=True,
    )
    imported_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    amount = Column(Numeric(18, 2), nullable=True)
    account = Column(String, nullable=True)
    datetime = Column(String, nullable=True)
    classification = Column(String, nullable=True)
    status = Column(String, nullable=False, default="imported")

    parsed_candidate = relationship(
        "ParsedTransactionCandidate",
        backref="misa_import_state",
    )
