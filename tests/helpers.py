import tempfile
from pathlib import Path

from yinyang_core.app import Core
from yinyang_core.config import Settings


def make_core(tmp=None, **kw):
    tmp = Path(tmp or tempfile.mkdtemp())
    s = Settings(db_path=str(tmp / "k.sqlite3"), audit_path=str(tmp / "audit.jsonl"),
                 shutdown_grace_s=0.5, task_timeout_s=2.0, **kw)
    return Core(s)
