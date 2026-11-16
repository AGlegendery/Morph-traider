"""Structured JSON logging with automatic credential/secret redaction."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Mapping

REDACTED_PLACEHOLDER = "[REDACTED]"
SENSITIVE_KEY_FRAGMENTS = (
    "secret",
    "token",
    "password",
    "passwd",
    "authorization",
    "api_key",
    "apikey",
    "cookie",
    "signature",
)


def redact_sensitive_data(value: Any) -> Any:
    """Recursively mask sensitive keys in mappings/lists before writing to logs or audit JSON."""
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_lower = str(key).lower()
            if any(fragment in key_lower for fragment in SENSITIVE_KEY_FRAGMENTS):
                sanitized[str(key)] = REDACTED_PLACEHOLDER
            else:
                sanitized[str(key)] = redact_sensitive_data(item)
        return sanitized
    if isinstance(value, (list, tuple)):
        return [redact_sensitive_data(elem) for elem in value]
    return value


class StructuredRedactingFormatter(logging.Formatter):
    """Lightweight single-line JSON formatter safe for shared-hosting WSGI error logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        structured_context = getattr(record, "context", None)
        if structured_context is not None:
            payload["context"] = redact_sensitive_data(structured_context)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=True)


def configure_app_logging(logger: logging.Logger, *, level: int = logging.INFO) -> logging.Logger:
    """Attach idempotent structured redacting formatter to the application logger."""
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setFormatter(StructuredRedactingFormatter())
    if not logger.handlers:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(StructuredRedactingFormatter())
        logger.addHandler(stream_handler)
    return logger
