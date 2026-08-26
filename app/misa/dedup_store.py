"""Database-backed dedup store tracking which candidate rows have already
been imported into MISA.

The state is stored in the `misa_import_state` table so it lives alongside
the parsed candidates and is automatically backed up with the SQLite file.
See ai/update_misa_implementation/update_misa_design.md §4.3 for the schema
and semantics implemented here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.misa_import_state import MisaImportState

_IMPORTED_STATUS = "imported"


def _to_uuid(value: Any) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _ensure_table_exists(session: Session) -> None:
    """Create the `misa_import_state` table if it is missing.

    This makes the runner safe to run against an older database that was
    created before the MISA import state table was introduced. It is a
    no-op when the table already exists.
    """
    engine = session.bind
    if engine is None:
        return
    if inspect(engine).has_table(MisaImportState.__tablename__):
        return
    Base.metadata.create_all(
        bind=engine,
        tables=[MisaImportState.__table__],
        checkfirst=True,
    )


class DedupStore:
    """Tracks imported candidate ids in the `misa_import_state` table.

    Only entries with `status == "imported"` are treated as already done.
    Failed attempts must never be written via this store, so they remain
    eligible for retry on the next run (requirements.md §4).
    """

    def __init__(self, db: Optional[Session] = None):
        self._provided_db = db
        self._db: Optional[Session] = db
        _ensure_table_exists(self._session())

    def _session(self) -> Session:
        if self._db is None:
            from app.db.session import SessionLocal

            self._db = SessionLocal()
        return self._db

    def is_imported(self, candidate_id: Any) -> bool:
        """Return True if `candidate_id` is recorded as successfully imported."""
        session = self._session()
        stmt = select(MisaImportState).where(
            MisaImportState.parsed_candidate_id == _to_uuid(candidate_id),
            MisaImportState.status == _IMPORTED_STATUS,
        )
        return session.execute(stmt).scalar_one_or_none() is not None

    def mark_imported(
        self, candidate_id: Any, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record `candidate_id` as successfully imported and persist to the DB.

        `metadata` is merged into the stored row (e.g. `imported_at`,
        `amount`, `account`, `datetime`, `classification`) alongside
        `status: "imported"`.
        """
        metadata = dict(metadata or {})
        imported_at = metadata.get("imported_at")
        if isinstance(imported_at, str):
            imported_at = datetime.fromisoformat(imported_at)
        elif imported_at is None:
            imported_at = datetime.now(timezone.utc)

        state = MisaImportState(
            parsed_candidate_id=_to_uuid(candidate_id),
            imported_at=imported_at,
            amount=metadata.get("amount"),
            account=metadata.get("account"),
            datetime=metadata.get("datetime"),
            classification=metadata.get("classification"),
            status=_IMPORTED_STATUS,
        )
        session = self._session()
        session.merge(state)
        session.commit()

    def close(self) -> None:
        """Close the underlying session if it was created by this store."""
        if self._db is not None and self._db is not self._provided_db:
            self._db.close()
            self._db = None
