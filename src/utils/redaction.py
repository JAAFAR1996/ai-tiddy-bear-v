"""Utility helpers for masking sensitive data before logging."""
from __future__ import annotations

import re
from typing import Any

SECRET_PATTERNS = (
    re.compile(r"(?i)(sk-[a-z0-9]{8,})"),
    re.compile(r"(?i)(sk_?[a-z0-9\-]{16,})"),
    re.compile(r"(?i)(proj-[a-z0-9_-]{8,})"),
    re.compile(r"(?i)(eyJ[0-9A-Za-z_-]+\.[0-9A-Za-z_-]+\.[0-9A-Za-z_-]+)"),
    re.compile(r"(?i)(?:api|auth|access|secret|token)[\s:=]+([A-Za-z0-9\-_]{6,})"),
)

MASK = "***MASKED***"


def _mask_match(match: re.Match[str]) -> str:
    value = match.group(1)
    if not value:
        return MASK
    keep = 4 if len(value) > 8 else 1
    return f"{value[:keep]}{MASK}"


def sanitize_text(text: str | None) -> str | None:
    if not text:
        return text
    sanitized = text
    for pattern in SECRET_PATTERNS:
        sanitized = pattern.sub(_mask_match, sanitized)
    return sanitized


def sanitize_mapping(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: sanitize_mapping(v) for k, v in data.items()}
    if isinstance(data, list):
        return [sanitize_mapping(item) for item in data]
    if isinstance(data, tuple):
        return tuple(sanitize_mapping(item) for item in data)
    if isinstance(data, set):
        return {sanitize_mapping(item) for item in data}
    if isinstance(data, str):
        return sanitize_text(data)
    return data


def redact_in_place(mapping: dict[str, Any]) -> dict[str, Any]:
    for key, value in list(mapping.items()):
        mapping[key] = sanitize_mapping(value)
    return mapping
