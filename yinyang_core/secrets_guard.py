"""Erkennt und schwärzt geheimnisähnliche Zeichenfolgen (für Audit-Log und Wissensspeicher)."""
import re

_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token|password|passwd)\b\s*[:=]\s*\S+"),
]
_SENSITIVE_KEYS = ("key", "secret", "token", "password", "passwd", "authorization")
REDACTED = "[GESCHWÄRZT]"


def contains_secret(text: str) -> bool:
    return any(p.search(text) for p in _PATTERNS)


def redact(value, _depth=0):
    """Schwärzt Geheimnisse rekursiv in str-/dict-/list-Werten."""
    if _depth > 6:
        return REDACTED
    if isinstance(value, str):
        out = value
        for p in _PATTERNS:
            out = p.sub(REDACTED, out)
        return out
    if isinstance(value, dict):
        return {
            k: (REDACTED if any(s in str(k).lower() for s in _SENSITIVE_KEYS) else redact(v, _depth + 1))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(v, _depth + 1) for v in value]
    return value
