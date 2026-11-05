"""Minimal HTTP API (stdlib). Bind to localhost only; there is no authentication."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .orchestrator import TaskRejected
from .permissions import PermissionDenied

MAX_BODY = 16_384


def make_handler(core):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # audit log is used instead
            pass

        def _send(self, code, body):
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                raise TaskRejected("body too large", 413)
            try:
                obj = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                raise TaskRejected("invalid JSON")
            if not isinstance(obj, dict):
                raise TaskRejected("JSON object expected")
            return obj

        def do_GET(self):
            if self.path == "/health":
                h = core.lifecycle.health()
                h["provider"] = {"name": core.provider.name, "is_mock": core.provider.is_mock}
                return self._send(200 if h["ok"] else 503, h)
            if self.path == "/approvals":
                return self._send(200, {"approvals": [r.to_dict() for r in core.workflow.list()]})
            self._send(404, {"error": "not found"})

        def do_POST(self):
            try:
                if self.path == "/tasks":
                    b = self._body()
                    return self._send(200, core.orchestrator.submit(b.get("task"), b.get("agent")))
                if self.path.startswith("/approvals/") and self.path.endswith("/decision"):
                    b = self._body()
                    rid = int(self.path.split("/")[2])
                    req = core.workflow.decide(rid, b.get("decision") == "approve",
                                               str(b.get("decided_by", "")), bool(b.get("explicit")))
                    return self._send(200, req.to_dict())
                if self.path == "/reports/weekly":
                    if core.lifecycle.state != "running":
                        raise TaskRejected("service is not running", 503)
                    return self._send(200, core.reports.generate())
                self._send(404, {"error": "not found"})
            except TaskRejected as e:
                self._send(e.code, {"error": str(e)})
            except PermissionDenied as e:
                self._send(403, {"error": str(e)})
            except (KeyError, ValueError, IndexError) as e:
                self._send(400, {"error": f"bad request: {type(e).__name__}"})
            except Exception as e:
                core.audit.write("api_error", error=type(e).__name__)
                self._send(500, {"error": "internal error"})

    return Handler


def make_server(core, host=None, port=None) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host or core.settings.host, core.settings.port if port is None else port),
                               make_handler(core))
