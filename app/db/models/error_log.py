import uuid
from sqlalchemy import Column, String, Text, TIMESTAMP, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class ErrorLog(Base):
    __tablename__ = "error_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_id = Column(UUID(as_uuid=True), ForeignKey("email_raw.id"), nullable=True)

    error_type = Column(String, nullable=False)
    stack = Column(Text, nullable=False)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())