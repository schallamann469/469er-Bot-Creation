"""Konfiguration über Umgebungsvariablen. Es werden keine Geheimnisse benötigt oder protokolliert."""
import os
from dataclasses import dataclass, field
from typing import Tuple


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8469
    db_path: str = "data/knowledge.sqlite3"
    audit_path: str = "data/audit.jsonl"
    provider: str = "mock"
    max_task_chars: int = 2000
    task_timeout_s: float = 10.0
    max_retries: int = 1
    shutdown_grace_s: float = 5.0
    max_workers: int = 4
    # Einträge der Form "name=https://url"; standardmäßig leer (kein Netzwerkzugriff).
    report_sources: Tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_env(cls, env=None) -> "Settings":
        e = os.environ if env is None else env
        d = cls()
        sources = tuple(s.strip() for s in e.get("YY_REPORT_SOURCES", "").split(",") if s.strip())
        return cls(
            host=e.get("YY_HOST", d.host),
            port=int(e.get("YY_PORT", d.port)),
            db_path=e.get("YY_DB_PATH", d.db_path),
            audit_path=e.get("YY_AUDIT_PATH", d.audit_path),
            provider=e.get("YY_PROVIDER", d.provider),
            max_task_chars=int(e.get("YY_MAX_TASK_CHARS", d.max_task_chars)),
            task_timeout_s=float(e.get("YY_TASK_TIMEOUT_S", d.task_timeout_s)),
            max_retries=int(e.get("YY_MAX_RETRIES", d.max_retries)),
            shutdown_grace_s=float(e.get("YY_SHUTDOWN_GRACE_S", d.shutdown_grace_s)),
            max_workers=int(e.get("YY_MAX_WORKERS", d.max_workers)),
            report_sources=sources,
        )
