import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Event

from ai_core.agents import AniForge, Visionary, YinAndYang
from ai_core.approvals import ApprovalManager, ApprovalStatus, PatchProposal
from ai_core.api import create_server
from ai_core.code_proposals import CodeProposalService
from ai_core.knowledge import KnowledgeStore
from ai_core.providers import MockProvider
from ai_core.service import CoreService


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = KnowledgeStore(Path(self.temp.name) / "knowledge.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_only_confirmed_non_secret_knowledge_is_stored(self):
        with self.assertRaises(PermissionError):
            self.store.add_confirmed("finding", "unconfirmed")
        with self.assertRaises(ValueError):
            self.store.add_confirmed("finding", "api_key=example-secret", confirmed=True)
        item_id = self.store.add_confirmed(
            "decision", "Use local SQLite.", confirmed=True
        )
        self.assertEqual(self.store.list_confirmed()[0]["id"], item_id)
        self.assertTrue(self.store.health_check())

    def test_weekly_report_is_saved_with_source_and_retrieval_time(self):
        service = CoreService(str(Path(self.temp.name) / "reports.sqlite3"))
        report = service.visionary_report.generate_weekly(
            [
                {
                    "source": "https://example.test/updates",
                    "retrieved_at": "2026-11-05T12:00:00Z",
                    "summary": "A source update, supplied by the caller.",
                }
            ]
        )
        self.assertIn("https://example.test/updates", report["content"])
        self.assertIn("2026-11-05T12:00:00Z", report["content"])
        with service.store._connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM weekly_reports").fetchone()[0], 1)
        with self.assertRaises(ValueError):
            service.visionary_report.generate_weekly(
                [{"source": "https://example.test", "retrieved_at": "yesterday", "summary": "x"}]
            )


class ApprovalTests(unittest.TestCase):
    def test_action_tiers_and_patch_proposals(self):
        approvals = ApprovalManager()
        self.assertEqual(approvals.authorize("analyze"), ApprovalStatus.ALLOWED)
        self.assertEqual(approvals.authorize("test"), ApprovalStatus.APPROVAL_REQUIRED)
        self.assertEqual(
            approvals.authorize("test", explicitly_allowed=True, isolated=True),
            ApprovalStatus.ALLOWED,
        )
        self.assertEqual(
            approvals.authorize("modify_files", approved=True), ApprovalStatus.ALLOWED
        )
        self.assertEqual(
            approvals.authorize("delete_data", approved=True), ApprovalStatus.FORBIDDEN
        )
        proposal = PatchProposal("diff --git ...")
        self.assertEqual(proposal.status, ApprovalStatus.APPROVAL_REQUIRED)


class AgentTests(unittest.TestCase):
    def test_roles_and_ani_forge_are_separate(self):
        general = YinAndYang()
        ani_forge = AniForge()
        self.assertIsNone(general.plan("task")["delegated_to"])
        self.assertFalse(ani_forge.production_actions_enabled)
        self.assertFalse(hasattr(ani_forge, "knowledge"))
        self.assertEqual(ani_forge.submit("request")["status"], "placeholder")
        options = Visionary().improvement_options("problem")
        self.assertEqual(len(options), 2)
        self.assertIn("creative", options[1].name.lower())
        self.assertEqual(
            Visionary().review("change", authored_by="Visionär")["status"],
            "needs_independent_reviewer",
        )

    def test_provider_is_explicitly_a_mock(self):
        self.assertIn("MOCK", MockProvider().generate("hello", timeout=1))
        self.assertEqual(MockProvider.name, "mock")


class CodeProposalTests(unittest.TestCase):
    def test_real_provider_output_is_a_non_applied_proposal(self):
        class DraftProvider:
            name = "test-provider"

            def draft_code(self, task, context, *, timeout):
                self.asserted = (task, context, timeout)
                return "def answer():\n    return 42\n"

        provider = DraftProvider()
        proposal = CodeProposalService(provider).create(
            "Write a helper", "Use a small pure function."
        )
        self.assertEqual(proposal.provider, "test-provider")
        self.assertEqual(proposal.status, "approval_required")
        self.assertFalse(proposal.applied)
        self.assertIn("return 42", proposal.content)
        self.assertEqual(provider.asserted[:2], ("Write a helper", "Use a small pure function."))
        self.assertGreater(provider.asserted[2], 0)

    def test_mock_disclosure_and_input_and_output_guards(self):
        proposal = CodeProposalService().create("Write a function")
        self.assertEqual(proposal.provider, "mock")
        self.assertIn("MOCK", proposal.content)
        self.assertFalse(proposal.applied)
        with self.assertRaises(ValueError):
            CodeProposalService().create("api_key=do-not-send")
        with self.assertRaises(ValueError):
            CodeProposalService().create("Write code", "access_token=hidden")

        class SecretProvider:
            name = "test"

            def draft_code(self, task, context, *, timeout):
                return "secret=leaked"

        with self.assertRaises(ValueError):
            CodeProposalService(SecretProvider()).create("Write code")


class LifecycleTests(unittest.TestCase):
    def test_stop_rejects_new_tasks_and_waits_for_active_work(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        service = CoreService(str(Path(temp.name) / "lifecycle.sqlite3"))
        entered, release = Event(), Event()

        class BlockingProvider:
            name = "test"

            def generate(self, prompt, *, timeout):
                entered.set()
                release.wait(timeout=min(timeout, 2))
                return "done"

        service.coordinator.provider = BlockingProvider()
        service.start()
        worker = threading.Thread(target=service.submit_task, args=("test task",))
        worker.start()
        self.assertTrue(entered.wait(timeout=1))
        self.assertFalse(service.stop(timeout=0))
        with self.assertRaises(RuntimeError):
            service.submit_task("new task")
        release.set()
        worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertTrue(service.stop(timeout=1))


class APITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        service = CoreService(str(Path(self.temp.name) / "api.sqlite3"))
        self.service = service
        self.server = create_server(service, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.connection = HTTPConnection("127.0.0.1", self.server.server_address[1])

    def tearDown(self):
        self.connection.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def test_health_and_task_submission(self):
        self.connection.request("GET", "/health")
        response = self.connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertTrue(json.loads(response.read())["accepting_tasks"])

        self.connection.request(
            "POST", "/tasks", body=json.dumps({"task": "Plan a small change."}),
            headers={"Content-Type": "application/json"},
        )
        response = self.connection.getresponse()
        payload = json.loads(response.read())
        self.assertEqual(response.status, 200)
        self.assertEqual(payload["provider"], "mock")
        self.assertIn("MOCK", payload["response"])

    def test_weekly_report_api_and_source_validation(self):
        body = {
            "sources": [
                {
                    "source": "https://example.test/weekly",
                    "retrieved_at": "2026-11-05T12:00:00Z",
                    "summary": "Caller-supplied snapshot.",
                }
            ]
        }
        self.connection.request(
            "POST", "/reports/weekly", body=json.dumps(body),
            headers={"Content-Type": "application/json"},
        )
        response = self.connection.getresponse()
        report = json.loads(response.read())
        self.assertEqual(response.status, 201)
        self.assertIn("2026-11-05T12:00:00Z", report["content"])

    def test_code_proposal_endpoint_never_applies_mock_draft(self):
        self.connection.request(
            "POST",
            "/proposals/code",
            body=json.dumps({"task": "Write a helper"}),
            headers={"Content-Type": "application/json"},
        )
        response = self.connection.getresponse()
        proposal = json.loads(response.read())
        self.assertEqual(response.status, 200)
        self.assertEqual(proposal["status"], "approval_required")
        self.assertEqual(proposal["provider"], "mock")
        self.assertFalse(proposal["applied"])
        self.assertIn("MOCK", proposal["content"])
        self.assertFalse(list(Path(self.temp.name).glob("*.py")))

    def test_malformed_task_and_stop(self):
        self.connection.request(
            "POST", "/tasks", body=json.dumps({"task": "api_key=not-a-secret"}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(self.connection.getresponse().status, 400)
        self.connection.request("POST", "/stop", body=b"")
        self.assertEqual(self.connection.getresponse().status, 200)
        self.connection.request(
            "POST", "/tasks", body=json.dumps({"task": "later"}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(self.connection.getresponse().status, 503)


if __name__ == "__main__":
    unittest.main()
