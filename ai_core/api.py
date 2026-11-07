"""Small JSON HTTP API implemented with the Python standard library."""

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Type

from .service import CoreService


def handler_for(service: CoreService) -> Type[BaseHTTPRequestHandler]:
    class APIHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:
            if self.path != "/health":
                self._respond(404, {"error": "Not found"})
                return
            self._respond(200, service.health())

        def do_POST(self) -> None:
            if self.path == "/stop":
                stopped = service.stop()
                self._respond(200 if stopped else 504, {"stopped": stopped})
                return
            if self.path not in {
                "/tasks",
                "/language",
                "/language/stream",
                "/reports/weekly",
                "/proposals/code",
            }:
                self._respond(404, {"error": "Not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 16_384:
                    raise ValueError("Request body must be between 1 and 16384 bytes.")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError("Request body must be a JSON object.")
                if self.path == "/tasks":
                    result = service.submit_task(body.get("task"))
                    self._respond(200, result)
                elif self.path == "/language":
                    result = service.generate_language_response(body.get("prompt"))
                    self._respond(200, result)
                elif self.path == "/language/stream":
                    prompt = body.get("prompt")
                    if not isinstance(prompt, str):
                        raise ValueError("prompt must be text.")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Transfer-Encoding", "chunked")
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    try:
                        for text in service.stream_language_response(prompt):
                            chunk = text.encode("utf-8")
                            if chunk:
                                self.wfile.write(f"{len(chunk):X}\r\n".encode("ascii"))
                                self.wfile.write(chunk + b"\r\n")
                                self.wfile.flush()
                        self.wfile.write(b"0\r\n\r\n")
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        logging.getLogger("ai_core.api").info(
                            "Streaming client disconnected"
                        )
                    except Exception:
                        logging.getLogger("ai_core.api").exception(
                            "Language stream failed after response started"
                        )
                        try:
                            self.wfile.write(b"0\r\n\r\n")
                            self.wfile.flush()
                        except (BrokenPipeError, ConnectionResetError):
                            pass
                elif self.path == "/proposals/code":
                    result = service.propose_code(
                        body.get("task"), body.get("context", "")
                    )
                    self._respond(200, result)
                else:
                    snapshots = body.get("sources", [])
                    if not isinstance(snapshots, list):
                        raise ValueError("sources must be a list.")
                    self._respond(201, service.generate_weekly_report(snapshots))
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                self._respond(400, {"error": str(error)})
            except RuntimeError as error:
                self._respond(503, {"error": str(error)})
            except Exception:
                logging.getLogger("ai_core.api").exception("Task request failed")
                self._respond(500, {"error": "Task could not be completed."})

        def _respond(self, status: int, payload: dict[str, object]) -> None:
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args: object) -> None:
            logging.getLogger("ai_core.api").info(format, *args)

    return APIHandler


def create_server(service: CoreService, host: str = "127.0.0.1", port: int = 8000):
    service.start()
    return ThreadingHTTPServer((host, port), handler_for(service))
