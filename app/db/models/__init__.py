"""
Import all models to ensure they're registered with SQLAlchemy.
This prevents circular import issues and ensures relationships are properly initialized.
"""

from app.db.models.email_raw import EmailRaw
from app.db.models.parsed_candidate import ParsedTransactionCandidate, DebitCredit
from app.db.models.event import Event
from app.db.models.correlation_link import CorrelationLink
from app.db.models.error_log import ErrorLog
from app.db.models.audit_log import AuditLog

__all__ = [
    "EmailRaw",
    "ParsedTransactionCandidate",
    "DebitCredit",
    "Event",
    "CorrelationLink",
    "ErrorLog",
    "AuditLog",
]
