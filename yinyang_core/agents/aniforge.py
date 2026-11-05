"""AniForge: isolated minimal animation module.

Deliberately takes no store, provider, or other agent references: no shared
memory/data with other agents by default.
"""


class AniForgeAgent:
    name = "aniforge"

    def __init__(self):
        self._notes = []  # private to this agent

    def run(self, task: str) -> dict:
        self._notes.append(task)
        return {
            "agent": self.name,
            "status": "placeholder",
            "outline": ["define scene list", "define keyframes", "review with user"],
            "note": "Minimal placeholder: no animation is produced in this starter.",
        }
