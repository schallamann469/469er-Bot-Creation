"""Code drafting that returns reviewable text and never writes project files."""

import time
import uuid
from dataclasses import dataclass
from typing import Protocol

from .security import contains_secret, validate_task_text


class CodeDraftProvider(Protocol):
    name: str

    def draft_code(self, task: str, context: str, *, timeout: float) -> str: ...


class MockCodeDraftProvider:
    """Explicit placeholder that does not generate real code."""

    name = "mock"

    def draft_code(self, task: str, context: str, *, timeout: float) -> str:
        return (
            "[MOCK — kein Code generiert. Richte einen echten CodeDraftProvider ein, "
            "um Codeentwürfe zu erzeugen.]"
        )


@dataclass(frozen=True)
class CodeProposal:
    proposal_id: str
    status: str
    provider: str
    content: str
    applied: bool = False


class CodeProposalService:
    MAX_CONTEXT_LENGTH = 4000
    MAX_OUTPUT_LENGTH = 16_000
    MAX_SECONDS = 10.0

    def __init__(self, provider: CodeDraftProvider | None = None):
        self.provider = provider or MockCodeDraftProvider()

    def create(self, task: str, context: str = "") -> CodeProposal:
        validated_task = validate_task_text(task, max_length=2000)
        if not isinstance(context, str):
            raise ValueError("Context must be text.")
        if len(context) > self.MAX_CONTEXT_LENGTH:
            raise ValueError(
                f"Context exceeds the {self.MAX_CONTEXT_LENGTH}-character limit."
            )
        if contains_secret(context):
            raise ValueError("Context appears to contain a secret.")

        started = time.monotonic()
        draft = self.provider.draft_code(
            validated_task, context, timeout=self.MAX_SECONDS
        )
        if time.monotonic() - started > self.MAX_SECONDS:
            raise TimeoutError("Code drafting exceeded the configured time limit.")
        if not isinstance(draft, str) or not draft.strip():
            raise ValueError("The code provider returned an empty draft.")
        if len(draft) > self.MAX_OUTPUT_LENGTH:
            raise ValueError("The code provider output exceeds the size limit.")
        if contains_secret(draft):
            raise ValueError("Generated draft appears to contain a secret.")

        return CodeProposal(
            proposal_id=str(uuid.uuid4()),
            status="approval_required",
            provider=getattr(self.provider, "name", "custom"),
            content=draft,
        )
