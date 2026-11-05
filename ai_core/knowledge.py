"""Local SQLite storage for explicitly confirmed knowledge and reports."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .security import contains_secret


class KnowledgeStore:
    ALLOWED_KINDS = frozenset({"finding", "decision", "feedback"})
    MAX_ITEMS = 1000
    MAX_CONTENT_LENGTH = 2000
    MAX_REPORTS = 520
    MAX_REPORT_LENGTH = 20_000

    def __init__(self, path: str | Path = "data/knowledge.sqlite3"):
        self.path = Path(path)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS knowledge (
                    id INTEGER PRIMARY KEY,
                    kind TEXT NOT NULL CHECK (kind IN ('finding', 'decision', 'feedback')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS weekly_reports (
                    id INTEGER PRIMARY KEY,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY,
                    action TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    task_id TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )

    def health_check(self) -> bool:
        with self._connect() as connection:
            return connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"

    def add_confirmed(
        self, kind: str, content: str, *, confirmed: bool = False
    ) -> int:
        if not confirmed:
            raise PermissionError("Knowledge is stored only after explicit confirmation.")
        if kind not in self.ALLOWED_KINDS:
            raise ValueError(f"Unsupported knowledge kind: {kind}")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Knowledge content must not be empty.")
        if len(content) > self.MAX_CONTENT_LENGTH:
            raise ValueError("Knowledge content exceeds the storage limit.")
        if contains_secret(content):
            raise ValueError("Knowledge appears to contain a secret.")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            count = connection.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]
            if count >= self.MAX_ITEMS:
                raise OverflowError("Knowledge store is full; existing data is not deleted.")
            cursor = connection.execute(
                "INSERT INTO knowledge (kind, content, created_at) VALUES (?, ?, ?)",
                (kind, content.strip(), _now()),
            )
            return int(cursor.lastrowid)

    def list_confirmed(self, *, limit: int = 20) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(int(limit), 100))
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, kind, content, created_at FROM knowledge "
                "ORDER BY id DESC LIMIT ?",
                (bounded_limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def save_report(self, content: str) -> int:
        if not content.strip() or len(content) > self.MAX_REPORT_LENGTH or contains_secret(content):
            raise ValueError("Report is empty or appears to contain a secret.")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            count = connection.execute("SELECT COUNT(*) FROM weekly_reports").fetchone()[0]
            if count >= self.MAX_REPORTS:
                raise OverflowError("Report store is full; existing data is not deleted.")
            cursor = connection.execute(
                "INSERT INTO weekly_reports (content, created_at) VALUES (?, ?)",
                (content, _now()),
            )
            return int(cursor.lastrowid)

    def add_audit_event(self, action: str, outcome: str, task_id: str | None) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO audit_events (action, outcome, task_id, created_at) "
                "VALUES (?, ?, ?, ?)",
                (action, outcome, task_id, _now()),
            )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
