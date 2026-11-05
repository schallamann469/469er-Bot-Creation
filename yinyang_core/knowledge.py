"""Lokaler SQLite-Wissensspeicher. Nur ausdrücklich freigegebene Einträge; niemals Geheimnisse."""
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .secrets_guard import contains_secret

SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL CHECK (kind IN ('feedback','decision','knowledge')),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT NOT NULL,
    approved_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""
KINDS = ("feedback", "decision", "knowledge")


class KnowledgeError(Exception):
    pass


class KnowledgeStore:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self.init_schema()

    def init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def health(self) -> bool:
        with self._lock:
            return self._conn.execute("SELECT 1").fetchone()[0] == 1

    def add(self, kind: str, title: str, content: str, source: str,
            approved: bool = False, approved_by: Optional[str] = None) -> int:
        if kind not in KINDS:
            raise KnowledgeError(f"ungültige Art '{kind}'")
        if not approved or not approved_by:
            raise KnowledgeError("nur ausdrücklich freigegebene Einträge dürfen gespeichert werden")
        if not title or not content:
            raise KnowledgeError("Titel und Inhalt sind erforderlich")
        if contains_secret(title) or contains_secret(content) or contains_secret(source):
            raise KnowledgeError("Eintrag enthält vermutlich ein Geheimnis; Speichern abgelehnt")
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO knowledge(kind,title,content,source,approved_by,created_at) VALUES (?,?,?,?,?,?)",
                (kind, title, content, source, approved_by, _now()),
            )
            self._conn.commit()
            return cur.lastrowid

    def search(self, text: str, limit: int = 10) -> List[dict]:
        like = "%" + text.replace("%", r"\%").replace("_", r"\_") + "%"
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM knowledge WHERE title LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\' "
                "ORDER BY id DESC LIMIT ?", (like, like, max(1, min(limit, 50)))).fetchall()
        return [dict(r) for r in rows]

    def save_report(self, kind: str, body: str) -> int:
        if contains_secret(body):
            raise KnowledgeError("Bericht enthält vermutlich ein Geheimnis; Speichern abgelehnt")
        with self._lock:
            cur = self._conn.execute("INSERT INTO reports(kind,body,created_at) VALUES (?,?,?)", (kind, body, _now()))
            self._conn.commit()
            return cur.lastrowid

    def list_reports(self, kind: Optional[str] = None, limit: int = 10) -> List[dict]:
        with self._lock:
            if kind:
                rows = self._conn.execute("SELECT * FROM reports WHERE kind=? ORDER BY id DESC LIMIT ?", (kind, limit))
            else:
                rows = self._conn.execute("SELECT * FROM reports ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(r) for r in rows.fetchall()]

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
