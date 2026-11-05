"""Isolated placeholder for animation requests; it has no shared memory."""


class AniForge:
    name = "AniForge"
    production_actions_enabled = False

    def submit(self, request: str) -> dict[str, str]:
        return {
            "agent": self.name,
            "status": "placeholder",
            "request": request,
            "message": "AniForge is isolated; no story logic, shared memory, or production actions.",
        }
