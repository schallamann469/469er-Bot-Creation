"""Small audit trail that records action metadata, not sensitive content."""

import logging
from datetime import datetime, timezone


class AuditLog:
    def __init__(self, store=None, logger: logging.Logger | None = None):
        self._store = store
        self._logger = logger or logging.getLogger("ai_core.audit")

    def record(self, action: str, outcome: str, *, task_id: str | None = None) -> None:
        if self._store is not None:
            self._store.add_audit_event(action, outcome, task_id)
        self._logger.info(
            "action=%s outcome=%s task_id=%s at=%s",
            action,
            outcome,
            task_id or "-",
            datetime.now(timezone.utc).isoformat(),
        )
