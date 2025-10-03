"""
Utility modules for the AI Teddy Bear application.
Provides crypto, validation, text processing, and security utilities.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any, Dict, Tuple

__all__ = [
    "EncryptionService",
    "ValidationUtils",
    "DataValidator",
    "TextProcessor",
    "SafeTextAnalyzer",
    "SecurityUtils",
    "DateUtils",
    "TimeFormatter",
    "FileHandler",
    "SecureFileOperations",
]

_MODULE_ATTR_MAP: Dict[str, Tuple[str, str]] = {
    "EncryptionService": (".crypto_utils", "EncryptionService"),
    "ValidationUtils": (".validation_utils", "ValidationUtils"),
    "DataValidator": (".validation_utils", "DataValidator"),
    "TextProcessor": (".text_utils", "TextProcessor"),
    "SafeTextAnalyzer": (".text_utils", "SafeTextAnalyzer"),
    "SecurityUtils": (".security_utils", "SecurityUtils"),
    "DateUtils": (".date_utils", "DateUtils"),
    "TimeFormatter": (".date_utils", "TimeFormatter"),
    "FileHandler": (".file_utils", "FileHandler"),
    "SecureFileOperations": (".file_utils", "SecureFileOperations"),
}


def __getattr__(name: str) -> Any:
    if name not in _MODULE_ATTR_MAP:
        raise AttributeError(f"module 'src.utils' has no attribute '{name}'")

    module_path, attribute = _MODULE_ATTR_MAP[name]
    module = import_module(module_path, package=__name__)
    value = getattr(module, attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(list(globals().keys()) + __all__))