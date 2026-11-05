"""Visionär: technical right hand / referee. Proposes options; never approves its own changes.

Approval decisions are human-only (ApprovalWorkflow.decide rejects agent names), so Visionär
cannot approve its own or anyone else's changes."""
from ..permissions import ApprovalWorkflow


class VisionarAgent:
    name = "visionar"

    def __init__(self, workflow: ApprovalWorkflow):
        self._workflow = workflow

    def propose(self, task: str) -> dict:
        approaches = [
            {
                "name": "Measure first, then fix the hot path (conventional)",
                "unusual": False,
                "expected_benefit": "Targets the real bottleneck; low regression risk.",
                "cost_complexity": "Low: add timing/profiling, fix one hotspot.",
                "risks": ["Profile may not reflect production load"],
                "tests": ["Benchmark before/after", "Regression tests on touched code"],
            },
            {
                "name": "Cache or batch repeated work (moderate)",
                "unusual": False,
                "expected_benefit": "Fewer repeated computations/IO calls.",
                "cost_complexity": "Medium: invalidation rules and memory bounds.",
                "risks": ["Stale data", "Extra memory"],
                "tests": ["Cache hit/miss tests", "Invalidation tests", "Bounded-size test"],
            },
            {
                "name": "Record-and-replay shadow run (creative/unusual)",
                "unusual": True,
                "expected_benefit": "Replay recorded real inputs against old and new implementations "
                                    "to compare output and timing without touching production.",
                "cost_complexity": "High: recording layer, replay harness, diff tooling.",
                "risks": ["Recorded data may be sensitive", "Over-engineering for small problems"],
                "tests": ["Replay equivalence test", "Redaction test on recordings"],
            },
        ]
        return {
            "agent": self.name,
            "task": task,
            "status": "draft",
            "approaches": approaches,
            "tradeoffs": "Unusual does not mean better: the unusual option has the highest cost and "
                         "is only worthwhile if the conventional options are insufficient.",
            "patch_suggestion": "# DRAFT ONLY - no files were modified. Needs explicit approval to apply.\n",
            "requires_approval_to_apply": True,
        }

    def run(self, task: str) -> dict:
        result = self.propose(task)
        req = self._workflow.request("modify_file", f"Apply draft for: {task[:200]}", self.name)
        result["approval_request_id"] = req.id
        return result
