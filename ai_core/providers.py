"""Provider boundary; the only included implementation is explicitly a mock."""

from typing import Protocol


class LanguageModelProvider(Protocol):
    def generate(self, prompt: str, *, timeout: float) -> str: ...


class MockProvider:
    name = "mock"

    def generate(self, prompt: str, *, timeout: float) -> str:
        return f"[MOCK — no real AI response generated] Received {len(prompt)} characters."
