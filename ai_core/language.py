"""Language service and explicitly opt-in OpenAI-compatible provider."""

import json
import math
import os
import time
import urllib.error
import urllib.request
from typing import Iterator, Protocol
from urllib.parse import urlparse

from .providers import MockProvider
from .security import contains_secret, validate_task_text


class TextProvider(Protocol):
    name: str

    def generate(self, prompt: str, *, timeout: float) -> str: ...


class StreamingTextProvider(TextProvider, Protocol):
    def stream(
        self, prompt: str, *, system_prompt: str, timeout: float
    ) -> Iterator[str]: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


class OllamaProvider:
    """Local Ollama chat provider returning text as it is generated."""

    MAX_LINE_BYTES = 64_000

    def __init__(self, *, endpoint: str, model: str, timeout_seconds: float = 120):
        parsed = urlparse(endpoint)
        if parsed.scheme != "http" or parsed.hostname not in {
            "localhost",
            "127.0.0.1",
            "::1",
        }:
            raise ValueError("Ollama must be configured on a local HTTP endpoint.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Ollama endpoint must not contain credentials, query, or fragment.")
        if not model.strip():
            raise ValueError("Ollama model must not be empty.")
        self.endpoint = endpoint.rstrip("/") + "/api/chat"
        self.model = model.strip()
        self.timeout_seconds = timeout_seconds
        self.name = f"ollama:{self.model}"
        self._opener = urllib.request.build_opener(_NoRedirect)

    def stream(
        self, prompt: str, *, system_prompt: str, timeout: float
    ) -> Iterator[str]:
        body = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "stream": True,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._opener.open(
                request, timeout=min(timeout, self.timeout_seconds)
            ) as response:
                while True:
                    line = response.readline(self.MAX_LINE_BYTES + 1)
                    if not line:
                        break
                    if len(line) > self.MAX_LINE_BYTES:
                        raise ValueError("Ollama stream line exceeds the size limit.")
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                        text = event.get("message", {}).get("content", "")
                        done = event.get("done", False)
                    except (json.JSONDecodeError, AttributeError) as error:
                        raise ValueError("Ollama returned an invalid streaming response.") from error
                    if text:
                        if not isinstance(text, str):
                            raise ValueError("Ollama returned non-text content.")
                        yield text
                    if done:
                        break
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"Ollama request failed with HTTP {error.code}.") from None
        except urllib.error.URLError:
            raise RuntimeError("Ollama could not be reached; check that it is running locally.") from None

    def generate(self, prompt: str, *, timeout: float) -> str:
        return "".join(
            self.stream(
                prompt,
                system_prompt="Du bist ein hilfreicher Assistent.",
                timeout=timeout,
            )
        )


class OpenAICompatibleProvider:
    """Minimal Chat Completions client; credentials are kept in process memory."""

    name = "openai-compatible"
    MAX_RESPONSE_BYTES = 128_000

    def __init__(
        self,
        *,
        endpoint: str,
        model: str,
        api_key: str,
    ):
        parsed = urlparse(endpoint)
        local_hosts = {"localhost", "127.0.0.1", "::1"}
        if parsed.scheme != "https" and not (
            parsed.scheme == "http" and parsed.hostname in local_hosts
        ):
            raise ValueError("The language endpoint must use HTTPS (HTTP is limited to localhost).")
        if not parsed.hostname or not parsed.path or not model.strip() or not api_key.strip():
            raise ValueError("Language endpoint, model, and API key are required.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Endpoint URL must not contain credentials, query, or fragment.")
        self.endpoint = endpoint
        self.model = model.strip()
        self._api_key = api_key.strip()
        self.name = f"openai-compatible:{self.model}"
        self._opener = urllib.request.build_opener(_NoRedirect)

    def generate(self, prompt: str, *, timeout: float) -> str:
        body = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={
                "Authorization": "Bearer " + self._api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self._opener.open(request, timeout=max(0.1, timeout)) as response:
                raw = response.read(self.MAX_RESPONSE_BYTES + 1)
            if len(raw) > self.MAX_RESPONSE_BYTES:
                raise ValueError("Language provider response exceeds the size limit.")
            payload = json.loads(raw)
            content = payload["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Language provider returned an empty response.")
            return content.strip()
        except urllib.error.HTTPError as error:
            raise RuntimeError(
                f"Language provider request failed with HTTP {error.code}."
            ) from None
        except urllib.error.URLError:
            raise RuntimeError("Language provider could not be reached.") from None
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise ValueError("Language provider returned an invalid response.") from error


def provider_from_environment(environment: dict[str, str] | None = None) -> TextProvider:
    """Select an external provider only after explicit, complete opt-in."""
    settings = os.environ if environment is None else environment
    provider_name = settings.get("AI_LANGUAGE_PROVIDER", "mock").strip().lower()
    if provider_name == "mock":
        return MockProvider()
    if provider_name != "openai-compatible":
        raise ValueError("AI_LANGUAGE_PROVIDER must be 'mock' or 'openai-compatible'.")
    if settings.get("AI_LANGUAGE_EXTERNAL_ENABLED", "").strip().lower() != "true":
        raise ValueError(
            "External language requests require AI_LANGUAGE_EXTERNAL_ENABLED=true."
        )
    return OpenAICompatibleProvider(
        endpoint=settings.get("AI_LANGUAGE_ENDPOINT", ""),
        model=settings.get("AI_LANGUAGE_MODEL", ""),
        api_key=settings.get("AI_LANGUAGE_API_KEY", ""),
    )


class LanguageService:
    MAX_PROMPT_LENGTH = 8000
    MAX_RESPONSE_LENGTH = 16_000
    MAX_SECONDS = 10.0

    def __init__(
        self,
        provider: TextProvider | None = None,
        *,
        system_prompt: str = "Du bist ein hilfreicher Assistent. Antworte knapp und auf Deutsch.",
        max_seconds: float = 120.0,
    ):
        self.provider = provider if provider is not None else MockProvider()
        self.system_prompt = system_prompt
        self.max_seconds = max_seconds

    @property
    def provider_name(self) -> str:
        return getattr(self.provider, "name", "custom")

    @property
    def name(self) -> str:
        return self.provider_name

    def generate(self, prompt: str, *, timeout: float | None = None) -> str:
        validated = validate_task_text(prompt, max_length=self.MAX_PROMPT_LENGTH)
        requested_timeout = timeout if timeout is not None else self.max_seconds
        if not math.isfinite(requested_timeout) or requested_timeout <= 0:
            raise TimeoutError("Language request exceeded the configured time limit.")
        deadline = min(requested_timeout, self.max_seconds)
        started = time.monotonic()
        stream_method = getattr(self.provider, "stream", None)
        if stream_method is not None:
            response = "".join(
                stream_method(
                    validated,
                    system_prompt=self.system_prompt,
                    timeout=deadline,
                )
            )
        else:
            response = self.provider.generate(
                f"System instruction: {self.system_prompt}\n\n{validated}",
                timeout=deadline,
            )
        if time.monotonic() - started > deadline:
            raise TimeoutError("Language request exceeded the configured time limit.")
        if not isinstance(response, str) or not response.strip():
            raise ValueError("Language provider returned an empty response.")
        if len(response) > self.MAX_RESPONSE_LENGTH:
            raise ValueError("Language provider response exceeds the size limit.")
        if contains_secret(response):
            raise ValueError("Language provider response appears to contain a secret.")
        return response.strip()

    def stream(self, prompt: str) -> Iterator[str]:
        validated = validate_task_text(prompt, max_length=self.MAX_PROMPT_LENGTH)
        started = time.monotonic()
        total_chars = 0
        stream_method = getattr(self.provider, "stream", None)
        if stream_method is None:
            response = self.generate(validated)
            yield response
            return
        for text in stream_method(
            validated,
            system_prompt=self.system_prompt,
            timeout=self.max_seconds,
        ):
            if time.monotonic() - started > self.max_seconds:
                raise TimeoutError("Language stream exceeded the configured time limit.")
            if not isinstance(text, str) or contains_secret(text):
                raise ValueError("Language provider returned invalid or sensitive text.")
            total_chars += len(text)
            if total_chars > self.MAX_RESPONSE_LENGTH:
                raise ValueError("Language provider stream exceeds the size limit.")
            yield text

    def draft_code(self, task: str, context: str, *, timeout: float) -> str:
        validated_task = validate_task_text(task, max_length=2000)
        if not isinstance(context, str) or len(context) > self.MAX_PROMPT_LENGTH:
            raise ValueError("Code context must be text within the configured size limit.")
        if contains_secret(context):
            raise ValueError("Code context appears to contain a secret.")
        if isinstance(self.provider, MockProvider):
            return (
                "[MOCK — kein Code generiert. Richte einen echten Sprachprovider ein, "
                "um Codeentwürfe zu erzeugen.]"
            )
        prompt = (
            "Erstelle einen Codeentwurf als Klartext. Wende nichts an, führe nichts aus. "
            "Gib nur den Entwurf zurück.\n\n"
            f"Aufgabe:\n{validated_task}\n\nKontext:\n{context}"
        )
        return self.generate(prompt, timeout=timeout)
