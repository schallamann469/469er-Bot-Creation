"""Yin und Yang: allgemeiner Assistent/Koordinator. Plant und leitet nur bei Bedarf weiter."""
from typing import Optional

TECH_WORDS = ("code", "bug", "fehler", "refactor", "performance", "leistung", "engpass", "bottleneck", "langsam",
              "slow", "optimi", "architektur", "architecture", "test", "sql")
ANIMATION_WORDS = ("animation", "animate", "animier", "zeichentrick")  # nur Routing-Stichwörter; keine Fachlogik hier


class YinYangAgent:
    name = "yin_yang"

    def __init__(self, provider):
        self._provider = provider

    def plan(self, task: str) -> dict:
        t = task.lower()
        if any(w in t for w in ANIMATION_WORDS):
            target: Optional[str] = "aniforge"
        elif any(w in t for w in TECH_WORDS):
            target = "visionar"
        else:
            target = None  # direkt beantworten; kein Routing nötig
        steps = ["Aufgabe verstehen", "weiterleiten an " + target if target else "direkt antworten", "Ergebnis berichten"]
        return {"route_to": target, "steps": steps}

    def run(self, task: str) -> dict:
        plan = self.plan(task)
        return {
            "agent": self.name,
            "plan": plan,
            "answer": self._provider.generate(task) if plan["route_to"] is None else None,
            "provider": self._provider.name,
            "provider_is_mock": self._provider.is_mock,
        }
