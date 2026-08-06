"""Local JSON-backed dedup store tracking which candidate rows have already
been imported into MISA.

See ai/update_misa_implementation/update_misa_design.md §4.3 for the schema
and semantics implemented here.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Union

DEFAULT_STATE_FILE = "ai/update_misa_implementation/imported_state.json"

_IMPORTED_STATUS = "imported"


class DedupStore:
    """Tracks imported candidate ids in a local JSON file.

    Only entries with `status == "imported"` are treated as already done.
    Failed attempts must never be written via this store, so they remain
    eligible for retry on the next run (requirements.md §4).
    """

    def __init__(self, path: Union[str, os.PathLike] = DEFAULT_STATE_FILE):
        self.path = Path(path)
        self._data: Dict[str, Dict[str, Any]] = self._load()

    def _load(self) -> Dict[str, Dict[str, Any]]:
        if not self.path.exists():
            return {}
        with self.path.open("r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            return {}
        return json.loads(content)

    def is_imported(self, candidate_id: Any) -> bool:
        """Return True if `candidate_id` is recorded as successfully imported."""
        entry = self._data.get(str(candidate_id))
        return bool(entry) and entry.get("status") == _IMPORTED_STATUS

    def mark_imported(
        self, candidate_id: Any, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record `candidate_id` as successfully imported and persist to disk.

        `metadata` is merged into the stored entry (e.g. `imported_at`,
        `amount`, `account`) alongside `status: "imported"`.
        """
        entry = dict(metadata or {})
        entry["status"] = _IMPORTED_STATUS
        self._data[str(candidate_id)] = entry
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=self.path.parent, prefix=f".{self.path.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, sort_keys=True)
            os.replace(tmp_path, self.path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
