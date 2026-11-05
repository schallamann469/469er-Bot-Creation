"""Yin und Yang: general assistant/coordinator. Plans and routes only when appropriate."""
from typing import Optional

TECH_WORDS = ("code", "bug", "refactor", "performance", "bottleneck", "slow", "optimi", "architecture", "test", "sql")
ANIMATION_WORDS = ("animation", "animate", "animier")  # routing keywords only; no domain logic here


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
            target = None  # handle directly; no routing needed
        steps = ["understand task", "route to " + target if target else "answer directly", "report result"]
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
