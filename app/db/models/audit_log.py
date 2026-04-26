
import uuid
from sqlalchemy import Column, String, TIMESTAMP, Uuid, func, JSON
from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    action = Column(String, nullable=False)   # 'reprocess', 'purge', 'rebuild'
    target_id = Column(Uuid(as_uuid=True), nullable=True)
    extra_data = Column(JSON, nullable=True)

    timestamp = Column(TIMESTAMP(timezone=True), server_default=func.now())
