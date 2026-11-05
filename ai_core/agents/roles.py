"""General coordinator and technical reviewer roles."""

from dataclasses import dataclass


class YinAndYang:
    name = "Yin und Yang"

    def plan(self, task: str) -> dict[str, object]:
        return {
            "agent": self.name,
            "task": task,
            "steps": ["Aufgabe analysieren", "Vorschlag erstellen", "Ergebnis prüfen"],
            "delegated_to": None,
        }


@dataclass(frozen=True)
class Approach:
    name: str
    benefit: str
    complexity: str
    risks: str
    maintainability: str


class Visionary:
    name = "Visionär"

    def improvement_options(self, problem: str) -> list[Approach]:
        return [
            Approach(
                "Incremental change",
                "Fits existing interfaces and is easy to review.",
                "Low",
                "May leave some inefficiency in place.",
                "High",
            ),
            Approach(
                "Creative alternative: event-driven prototype",
                "Can decouple work and enable new workflows.",
                "High",
                "More moving parts and operational failure modes.",
                "Medium until conventions are established.",
            ),
        ]

    def review(self, proposal: str, *, authored_by: str) -> dict[str, str]:
        if authored_by == self.name:
            return {"status": "needs_independent_reviewer", "reviewer": self.name}
        return {"status": "review_required", "reviewer": self.name, "proposal": proposal}
