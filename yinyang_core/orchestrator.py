"""Orchestrierung: prüft Aufgaben, leitet nur an nötige Agenten weiter, begrenzt Zeit/Wiederholungen."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout


class TaskRejected(Exception):
    """Wird geworfen, wenn eine Aufgabe nicht angenommen werden kann (ungültig oder Dienst läuft nicht)."""

    def __init__(self, message, code=400):
        super().__init__(message)
        self.code = code


class Orchestrator:
    def __init__(self, settings, audit, agents: dict, lifecycle):
        self._s, self._audit, self._agents, self._lc = settings, audit, agents, lifecycle
        self._executor = ThreadPoolExecutor(max_workers=settings.max_workers, thread_name_prefix="task")

    def submit(self, task, agent=None) -> dict:
        if not self._lc.begin_task():
            raise TaskRejected("Dienst nimmt keine Aufgaben an", 503)
        try:
            return self._process(task, agent)
        finally:
            self._lc.end_task()

    def _process(self, task, agent):
        if not isinstance(task, str) or not task.strip():
            raise TaskRejected("Aufgabe muss ein nicht-leerer Text sein")
        if len(task) > self._s.max_task_chars:
            raise TaskRejected(f"Aufgabe überschreitet {self._s.max_task_chars} Zeichen")
        if agent is not None and agent not in self._agents:
            raise TaskRejected(f"unbekannter Agent '{agent}'")
        self._audit.write("task_received", task=task, agent=agent)
        steps = []
        target = agent or "yin_yang"
        result = self._run_bounded(target, task)
        steps.append(result)
        route = result.get("plan", {}).get("route_to") if target == "yin_yang" else None
        if route:  # nur an den nötigen Agenten weiterleiten
            steps.append(self._run_bounded(route, task))
        status = "error" if any(s.get("status") in ("error", "timeout") for s in steps) else "completed"
        self._audit.write("task_finished", status=status, agents=[s.get("agent") for s in steps])
        return {"status": status, "results": steps}

    def _run_bounded(self, name, task) -> dict:
        attempts = self._s.max_retries + 1
        for i in range(attempts):
            fut = self._executor.submit(self._agents[name].run, task)
            try:
                return fut.result(timeout=self._s.task_timeout_s)
            except FutureTimeout:
                fut.cancel()
                self._audit.write("task_timeout", agent=name)
                return {"agent": name, "status": "timeout", "error": "Aufgabe hat das Zeitlimit überschritten"}
            except Exception as exc:
                self._audit.write("task_error", agent=name, attempt=i + 1, error=type(exc).__name__)
        return {"agent": name, "status": "error", "error": "Agent nach Wiederholungen fehlgeschlagen"}

    def shutdown(self):
        self._executor.shutdown(wait=False, cancel_futures=True)
