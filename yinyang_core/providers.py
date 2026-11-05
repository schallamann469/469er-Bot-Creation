"""Model-provider interface. Only a MOCK is implemented; no API keys are read."""
from abc import ABC, abstractmethod


class ProviderError(Exception):
    pass


class ModelProvider(ABC):
    name = "abstract"
    is_mock = True

    @abstractmethod
    def generate(self, prompt: str) -> str: ...


class MockProvider(ModelProvider):
    """Deterministic placeholder. It does NOT produce real AI answers."""

    name = "mock"
    is_mock = True

    def generate(self, prompt: str) -> str:
        return f"[MOCK PROVIDER - not a real AI answer] received {len(prompt)} characters."


def get_provider(name: str) -> ModelProvider:
    if name == "mock":
        return MockProvider()
    raise ProviderError(
        f"provider '{name}' is not implemented in this starter; implement ModelProvider and register it here"
    )
