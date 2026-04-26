import uuid
from sqlalchemy import Column, String, Text, TIMESTAMP, Uuid, func, ForeignKey
from app.db.base import Base


class ErrorLog(Base):
    __tablename__ = "error_log"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_id = Column(Uuid(as_uuid=True), ForeignKey("email_raw.id"), nullable=True)

    error_type = Column(String, nullable=False)
    stack = Column(Text, nullable=False)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())