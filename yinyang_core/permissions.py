"""Autonomy tiers and the approval workflow.

Tier 1 AUTONOMOUS : read/analyze/plan/propose/report
Tier 2 BOUNDED    : bounded checks/tests in an isolated environment
Tier 3 APPROVAL   : file changes, dependency installs, config changes, deployment
Tier 4 PROHIBITED : deletion, external disclosure of confidential data,
                    publication, paid actions (only with explicit approval)

This starter never *executes* tier 3/4 actions. Approval is only recorded;
agents return drafts/patch suggestions.
"""
import itertools
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Dict, List, Optional


class Tier(IntEnum):
    AUTONOMOUS = 1
    BOUNDED = 2
    APPROVAL = 3
    PROHIBITED = 4


ACTION_TIERS: Dict[str, Tier] = {
    "read": Tier.AUTONOMOUS,
    "analyze": Tier.AUTONOMOUS,
    "plan": Tier.AUTONOMOUS,
    "propose": Tier.AUTONOMOUS,
    "report": Tier.AUTONOMOUS,
    "run_tests": Tier.BOUNDED,
    "run_check": Tier.BOUNDED,
    "modify_file": Tier.APPROVAL,
    "install_dependency": Tier.APPROVAL,
    "change_config": Tier.APPROVAL,
    "deploy": Tier.APPROVAL,
    "delete": Tier.PROHIBITED,
    "disclose_confidential": Tier.PROHIBITED,
    "publish": Tier.PROHIBITED,
    "paid_action": Tier.PROHIBITED,
}

AGENT_NAMES = ("yin_yang", "visionar", "aniforge")


def tier_of(action: str) -> Tier:
    """Unknown actions are treated as prohibited (fail closed)."""
    return ACTION_TIERS.get(action, Tier.PROHIBITED)


class PermissionDenied(Exception):
    pass


@dataclass
class ApprovalRequest:
    id: int
    action: str
    tier: int
    description: str
    requested_by: str
    status: str = "pending"  # pending | approved | rejected
    decided_by: Optional[str] = None
    explicit: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    decided_at: Optional[str] = None

    def to_dict(self) -> dict:
        return dict(self.__dict__)


class ApprovalWorkflow:
    """In-memory approval queue. Agents may request; only a non-agent may decide."""

    def __init__(self, audit=None):
        self._audit = audit
        self._ids = itertools.count(1)
        self._requests: Dict[int, ApprovalRequest] = {}
        self._lock = threading.Lock()

    def _log(self, event, **f):
        if self._audit:
            self._audit.write(event, **f)

    def check(self, action: str, approval_id: Optional[int] = None) -> None:
        """Raise PermissionDenied unless the action is allowed right now."""
        tier = tier_of(action)
        if tier <= Tier.BOUNDED:
            return
        req = self._requests.get(approval_id) if approval_id is not None else None
        ok = (
            req is not None
            and req.status == "approved"
            and req.action == action
            and (tier < Tier.PROHIBITED or req.explicit)
        )
        if not ok:
            self._log("permission_denied", action=action, tier=int(tier), approval_id=approval_id)
            raise PermissionDenied(f"action '{action}' (tier {int(tier)}) requires explicit approval")

    def request(self, action: str, description: str, requested_by: str) -> ApprovalRequest:
        tier = tier_of(action)
        with self._lock:
            req = ApprovalRequest(next(self._ids), action, int(tier), description, requested_by)
            self._requests[req.id] = req
        self._log("approval_requested", id=req.id, action=action, tier=int(tier), by=requested_by)
        return req

    def decide(self, request_id: int, approve: bool, decided_by: str, explicit: bool = False) -> ApprovalRequest:
        if decided_by in AGENT_NAMES:
            raise PermissionDenied("agents cannot approve requests")
        with self._lock:
            req = self._requests.get(request_id)
            if req is None:
                raise KeyError(request_id)
            if req.status != "pending":
                raise ValueError("request already decided")
            if decided_by == req.requested_by:
                raise PermissionDenied("requester cannot approve own request")
            if approve and req.tier >= Tier.PROHIBITED and not explicit:
                raise PermissionDenied("tier 4 actions need explicit=true approval")
            req.status = "approved" if approve else "rejected"
            req.decided_by = decided_by
            req.explicit = bool(explicit and approve)
            req.decided_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._log("approval_decided", id=request_id, status=req.status, by=decided_by)
        return req

    def get(self, request_id: int) -> Optional[ApprovalRequest]:
        return self._requests.get(request_id)

    def list(self) -> List[ApprovalRequest]:
        return list(self._requests.values())
