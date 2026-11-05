"""AniForge: isoliertes, minimales Animationsmodul.

Bekommt bewusst keinen Speicher, Anbieter oder andere Agenten-Referenzen:
standardmäßig kein gemeinsamer Speicher/keine gemeinsamen Daten mit anderen Agenten.
"""


class AniForgeAgent:
    name = "aniforge"

    def __init__(self):
        self._notes = []  # nur für diesen Agenten

    def run(self, task: str) -> dict:
        self._notes.append(task)
        return {
            "agent": self.name,
            "status": "placeholder",
            "outline": ["Szenenliste festlegen", "Keyframes festlegen", "mit Nutzer abstimmen"],
            "note": "Minimaler Platzhalter: Dieser Starter erzeugt keine Animation.",
        }
