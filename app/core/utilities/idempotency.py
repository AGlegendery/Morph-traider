"""Deterministic SHA-256 idempotency key helpers for signals, webhooks, and cron runs."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def derive_idempotency_key(namespace: str, payload: Any) -> str:
    """Derive a stable 64-hex SHA-256 idempotency key from canonicalized data."""
    clean_ns = namespace.strip().lower()
    if not clean_ns:
        raise ValueError("Idempotency namespace must be non-empty.")

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        ensure_ascii=True,
    )
    digest = hashlib.sha256(f"{clean_ns}:{canonical}".encode("utf-8")).hexdigest()
    return digest
