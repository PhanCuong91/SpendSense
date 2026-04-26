import uuid
from enum import Enum as PyEnum

from sqlalchemy import (
    Column,
    String,
    Text,
    Enum as SQLEnum,
    Numeric,
    TIMESTAMP,
    ForeignKey,
    Uuid,
)
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.db.models.correlation_link import CorrelationLink


class DebitCredit(str, PyEnum):
    debit = "debit"
    credit = "credit"
    spend = "spend"
    earn = "earn"


class ParsedTransactionCandidate(Base):
    __tablename__ = "parsed_transaction_candidate"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    email_id = Column(Uuid(as_uuid=True), ForeignKey("email_raw.id"), unique=True, nullable=False)

    amount = Column(Numeric(18, 2), nullable=True)
    currency = Column(String, nullable=True, default="SGD")
    datetime_sgt = Column(TIMESTAMP(timezone=True), nullable=True)

    inferred_sender = Column(String, nullable=True)
    inferred_receiver = Column(String, nullable=True)

    # raw_reference = Column(Text, nullable=True)
    debit_credit = Column(String, nullable=True)

    type_info = Column(String, nullable=True)

    email_raw = relationship("EmailRaw", backref="parsed_candidate")

    # Relationships to CorrelationLink
    correlation_links_debit = relationship(
        "CorrelationLink",
        back_populates="debit_candidate",
        foreign_keys=[CorrelationLink.debit_candidate_id],
        viewonly=False,
    )

    correlation_links_credit = relationship(
        "CorrelationLink",
        back_populates="credit_candidate",
        foreign_keys=[CorrelationLink.credit_candidate_id],
        viewonly=False,
    )