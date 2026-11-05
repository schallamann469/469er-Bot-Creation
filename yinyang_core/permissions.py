"""Autonomiestufen und Freigabe-Workflow.

Stufe 1 AUTONOMOUS : lesen/analysieren/planen/vorschlagen/berichten
Stufe 2 BOUNDED    : begrenzte Prüfungen/Tests in isolierter Umgebung
Stufe 3 APPROVAL   : Dateiänderungen, Abhängigkeiten installieren, Konfigurationsänderungen, Deployment
Stufe 4 PROHIBITED : Löschen, Weitergabe vertraulicher Daten nach außen,
                    Veröffentlichung, kostenpflichtige Aktionen (nur mit ausdrücklicher Freigabe)

Dieser Starter *führt* Aktionen der Stufen 3/4 nie aus. Freigaben werden nur
protokolliert; Agenten liefern Entwürfe/Patch-Vorschläge.
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
    """Unbekannte Aktionen gelten als verboten (im Zweifel gesperrt)."""
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
    """Freigabe-Warteschlange im Speicher. Agenten dürfen anfragen; nur Nicht-Agenten dürfen entscheiden."""

    def __init__(self, audit=None):
        self._audit = audit
        self._ids = itertools.count(1)
        self._requests: Dict[int, ApprovalRequest] = {}
        self._lock = threading.Lock()

    def _log(self, event, **f):
        if self._audit:
            self._audit.write(event, **f)

    def check(self, action: str, approval_id: Optional[int] = None) -> None:
        """Wirft PermissionDenied, wenn die Aktion jetzt nicht erlaubt ist."""
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
            raise PermissionDenied(f"Aktion '{action}' (Stufe {int(tier)}) erfordert ausdrückliche Freigabe")

    def request(self, action: str, description: str, requested_by: str) -> ApprovalRequest:
        tier = tier_of(action)
        with self._lock:
            req = ApprovalRequest(next(self._ids), action, int(tier), description, requested_by)
            self._requests[req.id] = req
        self._log("approval_requested", id=req.id, action=action, tier=int(tier), by=requested_by)
        return req

    def decide(self, request_id: int, approve: bool, decided_by: str, explicit: bool = False) -> ApprovalRequest:
        if decided_by in AGENT_NAMES:
            raise PermissionDenied("Agenten dürfen Anfragen nicht freigeben")
        with self._lock:
            req = self._requests.get(request_id)
            if req is None:
                raise KeyError(request_id)
            if req.status != "pending":
                raise ValueError("Anfrage wurde bereits entschieden")
            if decided_by == req.requested_by:
                raise PermissionDenied("Antragsteller darf die eigene Anfrage nicht freigeben")
            if approve and req.tier >= Tier.PROHIBITED and not explicit:
                raise PermissionDenied("Aktionen der Stufe 4 erfordern explicit=true")
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
