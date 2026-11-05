"""Visionär: technische rechte Hand / Schiedsrichter. Schlägt Optionen vor; gibt eigene Änderungen nie selbst frei.

Freigaben sind nur durch Menschen möglich (ApprovalWorkflow.decide lehnt Agentennamen ab);
Visionär kann also weder eigene noch fremde Änderungen freigeben."""
from ..permissions import ApprovalWorkflow


class VisionarAgent:
    name = "visionar"

    def __init__(self, workflow: ApprovalWorkflow):
        self._workflow = workflow

    def propose(self, task: str) -> dict:
        approaches = [
            {
                "name": "Erst messen, dann den kritischen Pfad beheben (konventionell)",
                "unusual": False,
                "expected_benefit": "Zielt auf den echten Engpass; geringes Regressionsrisiko.",
                "cost_complexity": "Gering: Zeitmessung/Profiling ergänzen, einen Hotspot beheben.",
                "risks": ["Profil entspricht evtl. nicht der Produktionslast"],
                "tests": ["Benchmark vorher/nachher", "Regressionstests für geänderten Code"],
            },
            {
                "name": "Wiederholte Arbeit cachen oder bündeln (moderat)",
                "unusual": False,
                "expected_benefit": "Weniger wiederholte Berechnungen/IO-Aufrufe.",
                "cost_complexity": "Mittel: Invalidierungsregeln und Speichergrenzen.",
                "risks": ["Veraltete Daten", "Mehr Speicherbedarf"],
                "tests": ["Cache-Treffer/-Fehlgriff-Tests", "Invalidierungstests", "Test der Größenbegrenzung"],
            },
            {
                "name": "Aufzeichnen-und-Wiederholen als Schattenlauf (kreativ/ungewöhnlich)",
                "unusual": True,
                "expected_benefit": "Aufgezeichnete echte Eingaben gegen alte und neue Implementierung abspielen, "
                                    "um Ausgabe und Laufzeit ohne Eingriff in die Produktion zu vergleichen.",
                "cost_complexity": "Hoch: Aufzeichnungsschicht, Replay-Rahmen, Diff-Werkzeuge.",
                "risks": ["Aufgezeichnete Daten können sensibel sein", "Überdimensioniert für kleine Probleme"],
                "tests": ["Replay-Äquivalenztest", "Schwärzungstest für Aufzeichnungen"],
            },
        ]
        return {
            "agent": self.name,
            "task": task,
            "status": "draft",
            "approaches": approaches,
            "tradeoffs": "Ungewöhnlich heißt nicht besser: Die ungewöhnliche Option hat den höchsten Aufwand "
                         "und lohnt sich nur, wenn die konventionellen Optionen nicht ausreichen.",
            "patch_suggestion": "# NUR ENTWURF - es wurden keine Dateien geändert. Anwenden erfordert ausdrückliche Freigabe.\n",
            "requires_approval_to_apply": True,
        }

    def run(self, task: str) -> dict:
        result = self.propose(task)
        req = self._workflow.request("modify_file", f"Entwurf anwenden für: {task[:200]}", self.name)
        result["approval_request_id"] = req.id
        return result
