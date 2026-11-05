"""Controlled start/stop lifecycle with startup health validation."""
import threading
import time


class StartupError(Exception):
    pass


class Lifecycle:
    def __init__(self, audit, checks=None, grace_s=5.0):
        self._audit, self._checks, self._grace = audit, dict(checks or {}), grace_s
        self._cv = threading.Condition()
        self.state = "created"  # created|running|stopping|stopped|failed
        self._inflight = 0

    def health(self) -> dict:
        results = {}
        for name, fn in self._checks.items():
            try:
                results[name] = bool(fn())
            except Exception:
                results[name] = False
        return {"state": self.state, "checks": results, "ok": self.state == "running" and all(results.values())}

    def start(self):
        failed = [n for n, ok in self.health()["checks"].items() if not ok]
        if failed:
            self.state = "failed"
            self._audit.write("startup_failed", failed_checks=failed)
            raise StartupError(f"startup health checks failed: {failed}")
        self.state = "running"
        self._audit.write("started")

    def begin_task(self) -> bool:
        with self._cv:
            if self.state != "running":
                return False
            self._inflight += 1
            return True

    def end_task(self):
        with self._cv:
            self._inflight -= 1
            self._cv.notify_all()

    def stop(self) -> bool:
        """Stop accepting tasks, wait up to grace for in-flight ones. Returns True if drained."""
        with self._cv:
            if self.state in ("stopped", "stopping"):
                return True
            self.state = "stopping"
        self._audit.write("stopping", inflight=self._inflight)
        deadline = time.monotonic() + self._grace
        with self._cv:
            while self._inflight > 0 and time.monotonic() < deadline:
                self._cv.wait(timeout=max(0.0, deadline - time.monotonic()))
            drained = self._inflight == 0
            self.state = "stopped"
        self._audit.write("stopped", drained=drained)
        return drained
