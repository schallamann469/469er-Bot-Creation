"""Validated YAML configuration for the local language model."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml


@dataclass(frozen=True)
class LanguageConfig:
    provider: str
    model: str
    system_prompt: str
    endpoint: str
    timeout_seconds: float


def load_language_config(path: str | Path = "config.yaml") -> LanguageConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as config_file:
        raw: Any = yaml.safe_load(config_file)
    if not isinstance(raw, dict):
        raise ValueError("config.yaml must contain a YAML mapping.")
    provider = raw.get("provider", "ollama")
    model = raw.get("model")
    system_prompt = raw.get("system_prompt")
    endpoint = os.getenv("OLLAMA_HOST", raw.get("endpoint", "http://127.0.0.1:11434"))
    timeout_seconds = raw.get("timeout_seconds", 120)
    if provider not in {"ollama", "mock"}:
        raise ValueError("Language provider in config.yaml must be 'ollama' or 'mock'.")
    if not isinstance(model, str) or not model.strip() or len(model) > 200:
        raise ValueError("config.yaml model must be a non-empty string of at most 200 characters.")
    if (
        not isinstance(system_prompt, str)
        or not system_prompt.strip()
        or len(system_prompt) > 2000
    ):
        raise ValueError(
            "config.yaml system_prompt must be a non-empty string of at most 2000 characters."
        )
    parsed_endpoint = urlparse(endpoint) if isinstance(endpoint, str) else None
    if (
        parsed_endpoint is None
        or parsed_endpoint.scheme != "http"
        or parsed_endpoint.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed_endpoint.username
        or parsed_endpoint.password
        or parsed_endpoint.query
        or parsed_endpoint.fragment
    ):
        raise ValueError("Ollama endpoint must use localhost HTTP.")
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
        raise ValueError("timeout_seconds must be a number.")
    if not 1 <= timeout_seconds <= 600:
        raise ValueError("timeout_seconds must be between 1 and 600.")
    return LanguageConfig(
        provider=provider,
        model=model.strip(),
        system_prompt=system_prompt.strip(),
        endpoint=endpoint.rstrip("/"),
        timeout_seconds=float(timeout_seconds),
    )
