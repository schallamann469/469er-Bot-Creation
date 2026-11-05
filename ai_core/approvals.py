"""Explicit authorization gates for actions the system may perform."""

from enum import Enum


class ApprovalStatus(str, Enum):
    ALLOWED = "allowed"
    APPROVAL_REQUIRED = "approval_required"
    FORBIDDEN = "forbidden"


class ApprovalManager:
    AUTONOMOUS = frozenset({"read", "analyze", "plan", "suggest", "report"})
    BOUNDED = frozenset({"test", "check"})
    APPROVAL_REQUIRED = frozenset(
        {"modify_files", "install_dependencies", "change_configuration", "deploy"}
    )
    FORBIDDEN = frozenset(
        {"delete_data", "send_confidential_data", "publish", "paid_action"}
    )

    def authorize(
        self,
        action: str,
        *,
        approved: bool = False,
        explicitly_allowed: bool = False,
        isolated: bool = False,
    ) -> ApprovalStatus:
        if action in self.FORBIDDEN:
            return ApprovalStatus.FORBIDDEN
        if action in self.AUTONOMOUS:
            return ApprovalStatus.ALLOWED
        if action in self.BOUNDED:
            return (
                ApprovalStatus.ALLOWED
                if explicitly_allowed and isolated
                else ApprovalStatus.APPROVAL_REQUIRED
            )
        if action in self.APPROVAL_REQUIRED and approved:
            return ApprovalStatus.ALLOWED
        if action in self.APPROVAL_REQUIRED:
            return ApprovalStatus.APPROVAL_REQUIRED
        return ApprovalStatus.FORBIDDEN


class PatchProposal:
    """Represents proposed code without applying it to the repository."""

    def __init__(self, patch: str):
        self.patch = patch
        self.status = ApprovalStatus.APPROVAL_REQUIRED

    def approve(self) -> None:
        self.status = ApprovalStatus.ALLOWED
