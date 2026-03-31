import uuid
from sqlalchemy import Column, String, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class EmailRaw(Base):
    __tablename__ = "email_raw"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    gmail_message_id = Column(String, unique=True, index=True, nullable=False)
    from_email = Column(Text, nullable=True)
    subject = Column(Text, nullable=True)
    body = Column(Text, nullable=True)

    internal_date = Column(TIMESTAMP(timezone=True), nullable=False)
    received_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relationship:
    # parsed_candidate = relationship("ParsedTransactionCandidate", back_populates="email_raw")