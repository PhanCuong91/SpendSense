import uuid
from sqlalchemy import (
    Column,
    String,
    Text,
    Numeric,
    TIMESTAMP,
    JSON,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class Event(Base):
    __tablename__ = "event"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    event_type = Column(String, nullable=False)    # Spend, Earn, InternalTransfer
    sender = Column(String, nullable=False)
    receiver = Column(String, nullable=False)

    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String, nullable=False, default="SGD")

    datetime_sgt = Column(TIMESTAMP(timezone=True), nullable=False)

    raw_email_ids = Column(JSON, nullable=False)   # list of IDs
    description = Column(Text, nullable=True)

    correlation_links = relationship("CorrelationLink", back_populates="event")