"""Schnittstelle für Modell-Anbieter. Nur ein MOCK ist implementiert; es werden keine API-Schlüssel gelesen."""
from abc import ABC, abstractmethod


class ProviderError(Exception):
    pass


class ModelProvider(ABC):
    name = "abstract"
    is_mock = True

    @abstractmethod
    def generate(self, prompt: str) -> str: ...


class MockProvider(ModelProvider):
    """Deterministischer Platzhalter. Er liefert KEINE echten KI-Antworten."""

    name = "mock"
    is_mock = True

    def generate(self, prompt: str) -> str:
        return f"[MOCK-ANBIETER - keine echte KI-Antwort] {len(prompt)} Zeichen empfangen."


def get_provider(name: str) -> ModelProvider:
    if name == "mock":
        return MockProvider()
    raise ProviderError(
        f"Anbieter '{name}' ist in diesem Starter nicht implementiert; ModelProvider implementieren und hier registrieren"
    )
