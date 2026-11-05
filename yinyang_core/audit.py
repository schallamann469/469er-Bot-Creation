"""Append-only JSONL audit log with secret redaction and value truncation."""
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from .secrets_guard import redact

_MAX_STR = 500


def _truncate(v):
    if isinstance(v, str):
        return v if len(v) <= _MAX_STR else v[:_MAX_STR] + "...[truncated]"
    if isinstance(v, dict):
        return {k: _truncate(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_truncate(x) for x in v]
    return v


class AuditLog:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def write(self, event: str, **fields) -> dict:
        record = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "event": event}
        record.update(_truncate(redact(fields)))
        line = json.dumps(record, ensure_ascii=False, default=str)
        with self._lock, self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        return record

    def read_all(self) -> list:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]
