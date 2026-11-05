"""Task coordination with strict input bounds and no repository write path."""

import time
import uuid

from .agents.roles import YinAndYang
from .audit import AuditLog
from .providers import LanguageModelProvider, MockProvider
from .security import validate_task_text


class TaskCoordinator:
    def __init__(
        self,
        *,
        provider: LanguageModelProvider | None = None,
        audit: AuditLog | None = None,
        max_task_seconds: float = 10.0,
    ):
        self.provider = provider or MockProvider()
        self.audit = audit or AuditLog()
        self.max_task_seconds = max_task_seconds
        self.max_retries = 0
        self.agent = YinAndYang()

    def process(self, task: str) -> dict[str, object]:
        validated = validate_task_text(task)
        task_id = str(uuid.uuid4())
        started = time.monotonic()
        self.audit.record("task", "started", task_id=task_id)
        try:
            plan = self.agent.plan(validated)
            remaining = self.max_task_seconds - (time.monotonic() - started)
            if remaining <= 0:
                raise TimeoutError("Task exceeded the configured time limit.")
            response = self.provider.generate(validated, timeout=remaining)
            elapsed = time.monotonic() - started
            if elapsed > self.max_task_seconds:
                raise TimeoutError("Task exceeded the configured time limit.")
            result = {
                "task_id": task_id,
                "status": "completed",
                "plan": plan,
                "provider": getattr(self.provider, "name", "custom"),
                "response": response,
            }
            self.audit.record("task", "completed", task_id=task_id)
            return result
        except Exception:
            self.audit.record("task", "failed", task_id=task_id)
            raise
