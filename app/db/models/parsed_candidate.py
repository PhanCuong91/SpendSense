
import uuid
from sqlalchemy import (
    Column,
    String,
    Text,
    Enum,
    Numeric,
    TIMESTAMP,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class DebitCredit(str, Enum):
    debit = "debit"
    credit = "credit"
    spend = "spend"
    earn = "earn"


class ParsedTransactionCandidate(Base):
    __tablename__ = "parsed_transaction_candidate"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    email_id = Column(UUID(as_uuid=True), ForeignKey("email_raw.id"), unique=True, nullable=False)

    amount = Column(Numeric(18, 2), nullable=True)
    currency = Column(String, nullable=True, default="SGD")
    datetime_sgt = Column(TIMESTAMP(timezone=True), nullable=True)

    inferred_sender = Column(String, nullable=True)
    inferred_receiver = Column(String, nullable=True)

    raw_reference = Column(Text, nullable=True)
    debit_credit = Column(Enum(DebitCredit), nullable=True)

    classification_hint = Column(String, nullable=True)

    email_raw = relationship("EmailRaw", backref="parsed_candidate")

    correlation_links_debit = relationship(
        "CorrelationLink",
        back_populates="debit_candidate",
        foreign_keys="CorrelationLink.debit_candidate_id",
    )

    correlation_links_credit = relationship(
        "CorrelationLink",
        back_populates="credit_candidate",
        foreign_keys="CorrelationLink.credit_candidate_id",
    )