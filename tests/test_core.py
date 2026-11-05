import json
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

from yinyang_core.agents import AniForgeAgent, VisionarAgent, YinYangAgent
from yinyang_core.api import make_server
from yinyang_core.knowledge import KnowledgeError, KnowledgeStore
from yinyang_core.lifecycle import Lifecycle, StartupError
from yinyang_core.audit import AuditLog
from yinyang_core.permissions import ApprovalWorkflow, PermissionDenied, Tier, tier_of
from yinyang_core.providers import MockProvider, ProviderError, get_provider
from yinyang_core.reports import WeeklyReportService, parse_sources
from yinyang_core.config import Settings
from .helpers import make_core


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.core = make_core()
        self.core.start()
        self.server = make_server(self.core, "127.0.0.1", 0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.core.stop()

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_health_reports_mock(self):
        code, body = self.call("GET", "/health")
        self.assertEqual(code, 200)
        self.assertTrue(body["ok"])
        self.assertTrue(body["provider"]["is_mock"])

    def test_task_routes_to_visionar_only(self):
        code, body = self.call("POST", "/tasks", {"task": "find the performance bottleneck in code"})
        self.assertEqual(code, 200)
        self.assertEqual([r["agent"] for r in body["results"]], ["yin_yang", "visionar"])
        v = body["results"][1]
        self.assertEqual(len(v["approaches"]), 3)
        self.assertTrue(any(a["unusual"] for a in v["approaches"]))
        self.assertEqual(v["status"], "draft")

    def test_simple_task_not_routed_and_marked_mock(self):
        _, body = self.call("POST", "/tasks", {"task": "hello"})
        self.assertEqual(len(body["results"]), 1)
        self.assertIn("MOCK", body["results"][0]["answer"])

    def test_validation(self):
        self.assertEqual(self.call("POST", "/tasks", {"task": ""})[0], 400)
        self.assertEqual(self.call("POST", "/tasks", {"task": "x" * 5000})[0], 400)
        self.assertEqual(self.call("POST", "/tasks", {"task": "a", "agent": "nope"})[0], 400)
        self.assertEqual(self.call("GET", "/nothing")[0], 404)

    def test_approval_endpoint_blocks_agents(self):
        _, body = self.call("POST", "/tasks", {"task": "a bug", "agent": "visionar"})
        rid = body["results"][0]["approval_request_id"]
        self.assertEqual(self.call("POST", f"/approvals/{rid}/decision",
                                   {"decision": "approve", "decided_by": "visionar"})[0], 403)
        code, r = self.call("POST", f"/approvals/{rid}/decision", {"decision": "approve", "decided_by": "alice"})
        self.assertEqual((code, r["status"]), (200, "approved"))

    def test_rejects_after_shutdown(self):
        self.core.lifecycle.stop()
        self.assertEqual(self.call("POST", "/tasks", {"task": "hi"})[0], 503)
        self.assertEqual(self.call("GET", "/health")[0], 503)

    def test_weekly_report_without_sources(self):
        code, r = self.call("POST", "/reports/weekly")
        self.assertEqual(code, 200)
        self.assertEqual(r["items"], [])


class StoreTests(unittest.TestCase):
    def test_schema_persist_and_search(self):
        path = tempfile.mkdtemp() + "/k.sqlite3"
        s = KnowledgeStore(path)
        s.add("decision", "Use SQLite", "local store", "user", approved=True, approved_by="alice")
        s.close()
        s2 = KnowledgeStore(path)  # persists on disk
        self.assertEqual(len(s2.search("SQLite")), 1)
        self.assertEqual(s2.search("100%"), [])
        tables = {r[0] for r in sqlite3.connect(path).execute("select name from sqlite_master where type='table'")}
        self.assertTrue({"knowledge", "reports"} <= tables)

    def test_rejects_unapproved_secret_and_bad_kind(self):
        s = KnowledgeStore(":memory:")
        with self.assertRaises(KnowledgeError):
            s.add("feedback", "t", "c", "u")
        with self.assertRaises(KnowledgeError):
            s.add("feedback", "t", "api_key = abc123", "u", approved=True, approved_by="a")
        with self.assertRaises(KnowledgeError):
            s.add("feedback", "t", "sk-abcdefghijklmnopqrstuv", "u", approved=True, approved_by="a")
        with self.assertRaises(KnowledgeError):
            s.add("chat", "t", "c", "u", approved=True, approved_by="a")
        self.assertEqual(s.search(""), [])


class PermissionTests(unittest.TestCase):
    def test_tiers(self):
        self.assertEqual(tier_of("analyze"), Tier.AUTONOMOUS)
        self.assertEqual(tier_of("run_tests"), Tier.BOUNDED)
        for a in ("modify_file", "install_dependency", "change_config", "deploy"):
            self.assertEqual(tier_of(a), Tier.APPROVAL)
        for a in ("delete", "disclose_confidential", "publish", "paid_action", "unknown"):
            self.assertEqual(tier_of(a), Tier.PROHIBITED)

    def test_check_and_workflow(self):
        w = ApprovalWorkflow()
        w.check("analyze")
        with self.assertRaises(PermissionDenied):
            w.check("modify_file")
        r = w.request("modify_file", "d", "visionar")
        with self.assertRaises(PermissionDenied):
            w.check("modify_file", r.id)  # pending
        with self.assertRaises(PermissionDenied):
            w.decide(r.id, True, "visionar")
        w.decide(r.id, True, "alice")
        w.check("modify_file", r.id)
        with self.assertRaises(PermissionDenied):
            w.check("deploy", r.id)  # approval is action-specific

    def test_tier4_needs_explicit(self):
        w = ApprovalWorkflow()
        r = w.request("delete", "d", "yin_yang")
        with self.assertRaises(PermissionDenied):
            w.decide(r.id, True, "alice")
        w.decide(r.id, True, "alice", explicit=True)
        w.check("delete", r.id)


class AgentTests(unittest.TestCase):
    def test_aniforge_isolated(self):
        a = AniForgeAgent()
        self.assertEqual(a.run("animation")["status"], "placeholder")
        for v in vars(a).values():
            self.assertNotIsInstance(v, (KnowledgeStore, ApprovalWorkflow, MockProvider, YinYangAgent, VisionarAgent))

    def test_yin_yang_routes_animation_without_logic(self):
        y = YinYangAgent(MockProvider())
        self.assertEqual(y.plan("make an animation")["route_to"], "aniforge")
        self.assertIsNone(y.plan("hello")["route_to"])

    def test_visionar_cannot_approve(self):
        w = ApprovalWorkflow()
        v = VisionarAgent(w)
        res = v.run("fix bug")
        self.assertFalse(hasattr(v, "review"))
        with self.assertRaises(PermissionDenied):
            w.decide(res["approval_request_id"], True, "visionar")
        self.assertEqual(w.get(res["approval_request_id"]).status, "pending")

    def test_provider(self):
        self.assertTrue(get_provider("mock").is_mock)
        with self.assertRaises(ProviderError):
            get_provider("openai")


class ReportTests(unittest.TestCase):
    def test_report_with_sources_and_errors(self):
        core = make_core()
        def fetch(url):
            if "bad" in url:
                raise OSError("x")
            return "news"
        svc = WeeklyReportService(core.store, core.audit,
                                  parse_sources(["a=https://x/a", "b=https://x/bad"]), fetch)
        r = svc.generate()
        self.assertEqual(r["items"][0]["excerpt"], "news")
        self.assertEqual(r["items"][1]["error"], "OSError")
        self.assertTrue(all(i["retrieved_at"] and i["url"] for i in r["items"]))
        self.assertEqual(len(core.store.list_reports("weekly_tech_update")), 1)

    def test_rejects_non_https(self):
        with self.assertRaises(ValueError):
            parse_sources(["a=http://x"])


class LifecycleTests(unittest.TestCase):
    def audit(self):
        return AuditLog(tempfile.mkdtemp() + "/a.jsonl")

    def test_startup_failure(self):
        lc = Lifecycle(self.audit(), {"db": lambda: False})
        with self.assertRaises(StartupError):
            lc.start()
        self.assertEqual(lc.state, "failed")
        self.assertFalse(lc.begin_task())

    def test_stop_waits_for_inflight(self):
        lc = Lifecycle(self.audit(), grace_s=2)
        lc.start()
        self.assertTrue(lc.begin_task())
        threading.Timer(0.2, lc.end_task).start()
        self.assertTrue(lc.stop())
        self.assertFalse(lc.begin_task())
        self.assertEqual(lc.state, "stopped")

    def test_stop_times_out(self):
        lc = Lifecycle(self.audit(), grace_s=0.1)
        lc.start()
        lc.begin_task()
        self.assertFalse(lc.stop())

    def test_timeout_and_retry_bounds(self):
        core = make_core()
        core.start()
        calls = []
        class Slow:
            def run(self, t):
                calls.append(1)
                time.sleep(0.5)
                return {"agent": "yin_yang", "status": "completed"}
        core.orchestrator._agents["yin_yang"] = Slow()
        core.orchestrator._s = Settings(task_timeout_s=0.1, max_retries=1)
        out = core.orchestrator.submit("hi")
        self.assertEqual(out["status"], "error")
        self.assertEqual(out["results"][0]["status"], "timeout")
        core.stop()

    def test_audit_redacts_secrets(self):
        core = make_core()
        core.audit.write("x", task="my token=abc123 and sk-abcdefghijklmnopqrstuv", api_key="zzz")
        rec = core.audit.read_all()[-1]
        self.assertNotIn("abc123", json.dumps(rec))
        self.assertNotIn("zzz", json.dumps(rec))
        core.stop()


if __name__ == "__main__":
    unittest.main()
