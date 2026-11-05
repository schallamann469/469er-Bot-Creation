"""Wiring: builds all components from Settings."""
from .agents import AniForgeAgent, VisionarAgent, YinYangAgent
from .audit import AuditLog
from .knowledge import KnowledgeStore
from .lifecycle import Lifecycle
from .orchestrator import Orchestrator
from .permissions import ApprovalWorkflow
from .providers import get_provider
from .reports import WeeklyReportService, parse_sources


class Core:
    def __init__(self, settings, fetch=None):
        self.settings = settings
        self.audit = AuditLog(settings.audit_path)
        self.store = KnowledgeStore(settings.db_path)
        self.provider = get_provider(settings.provider)
        self.workflow = ApprovalWorkflow(self.audit)
        self.agents = {
            "yin_yang": YinYangAgent(self.provider),
            "visionar": VisionarAgent(self.workflow),
            "aniforge": AniForgeAgent(),
        }
        self.lifecycle = Lifecycle(self.audit, {"knowledge_store": self.store.health}, settings.shutdown_grace_s)
        self.orchestrator = Orchestrator(settings, self.audit, self.agents, self.lifecycle)
        kw = {"fetch": fetch} if fetch else {}
        self.reports = WeeklyReportService(self.store, self.audit, parse_sources(settings.report_sources), **kw)

    def start(self):
        self.lifecycle.start()

    def stop(self):
        drained = self.lifecycle.stop()
        self.orchestrator.shutdown()
        self.store.close()
        return drained
