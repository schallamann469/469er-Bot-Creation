"""Input bounds and basic secret rejection for the local prototype."""

import re


_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(api[_ -]?key|password|passwd|secret|access[_ -]?token)\b\s*[:=]\s*\S+"),
    re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{20,})\b"),
)


def contains_secret(text: str) -> bool:
    return any(pattern.search(text) for pattern in _SECRET_PATTERNS)


def validate_task_text(text: str, *, max_length: int = 4000) -> str:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Task text must not be empty.")
    if len(text) > max_length:
        raise ValueError(f"Task text exceeds the {max_length}-character limit.")
    if contains_secret(text):
        raise ValueError("Task text appears to contain a secret.")
    return text.strip()
