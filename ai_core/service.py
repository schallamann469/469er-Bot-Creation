"""Application lifecycle and task acceptance state."""

import threading

from .audit import AuditLog
from .code_proposals import CodeDraftProvider, CodeProposalService
from .coordinator import TaskCoordinator
from .knowledge import KnowledgeStore
from .language import LanguageService, TextProvider
from .reports import VisionaryReport


class CoreService:
    def __init__(
        self,
        database_path: str = "data/knowledge.sqlite3",
        *,
        configured_sources: list[str] | None = None,
        code_provider: CodeDraftProvider | None = None,
        language_provider: TextProvider | None = None,
    ):
        self.store = KnowledgeStore(database_path)
        self.audit = AuditLog(self.store)
        self.language = LanguageService(language_provider)
        self.coordinator = TaskCoordinator(provider=self.language, audit=self.audit)
        self.code_proposals = CodeProposalService(
            code_provider if code_provider is not None else self.language
        )
        self.visionary_report = VisionaryReport(self.store, configured_sources)
        self._condition = threading.Condition()
        self._accepting = False
        self._active_tasks = 0

    def start(self) -> None:
        if not self.store.health_check():
            raise RuntimeError("SQLite health check failed; service was not started.")
        with self._condition:
            self._accepting = True

    def health(self) -> dict[str, object]:
        with self._condition:
            return {
                "status": "ok" if self.store.health_check() else "unhealthy",
                "accepting_tasks": self._accepting,
                "active_tasks": self._active_tasks,
                "language_provider": self.language.provider_name,
            }

    def submit_task(self, task: str) -> dict[str, object]:
        self._begin_work()
        try:
            return self.coordinator.process(task)
        finally:
            self._end_work()

    def generate_weekly_report(
        self, snapshots: list[dict[str, str]] | None = None
    ) -> dict[str, object]:
        self._begin_work()
        try:
            return self.visionary_report.generate_weekly(snapshots)
        finally:
            self._end_work()

    def propose_code(self, task: str, context: str = "") -> dict[str, object]:
        self._begin_work()
        try:
            proposal = self.code_proposals.create(task, context)
            return {
                "proposal_id": proposal.proposal_id,
                "status": proposal.status,
                "provider": proposal.provider,
                "content": proposal.content,
                "applied": proposal.applied,
            }
        finally:
            self._end_work()

    def generate_language_response(self, prompt: str) -> dict[str, str]:
        self._begin_work()
        try:
            return {
                "provider": self.language.provider_name,
                "response": self.language.generate(prompt),
            }
        finally:
            self._end_work()

    def _begin_work(self) -> None:
        with self._condition:
            if not self._accepting:
                raise RuntimeError("Service is stopped and is not accepting new work.")
            self._active_tasks += 1

    def _end_work(self) -> None:
        with self._condition:
            self._active_tasks -= 1
            self._condition.notify_all()

    def stop(self, timeout: float = 10.0) -> bool:
        with self._condition:
            self._accepting = False
            return self._condition.wait_for(
                lambda: self._active_tasks == 0, timeout=max(0.0, timeout)
            )
