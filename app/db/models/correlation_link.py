import uuid
from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class CorrelationLink(Base):
    __tablename__ = "correlation_link"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    debit_candidate_id = Column(UUID(as_uuid=True),
        ForeignKey("parsed_transaction_candidate.id", ondelete="CASCADE"),
        nullable=False
    )
    credit_candidate_id = Column(UUID(as_uuid=True),
        ForeignKey("parsed_transaction_candidate.id", ondelete="CASCADE"),
        nullable=False
    )

    event_id = Column(UUID(as_uuid=True),
        ForeignKey("event.id", ondelete="CASCADE"),
        nullable=True
    )

    debit_candidate = relationship(
        "ParsedTransactionCandidate",
        foreign_keys=[debit_candidate_id],
        back_populates="correlation_links_debit"
    )

    credit_candidate = relationship(
        "ParsedTransactionCandidate",
        foreign_keys=[credit_candidate_id],
        back_populates="correlation_links_credit"
    )

    event = relationship("Event", back_populates="correlation_links")