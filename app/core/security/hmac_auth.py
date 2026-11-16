"""Constant-time token and timestamped HMAC-SHA256 verification for cron & webhooks."""

from __future__ import annotations

import hashlib
import hmac
import time

from app.core.exceptions import SecurityAuthorizationError


def verify_bearer_or_secret_token(provided_token: str | None, expected_secret: str | None) -> None:
    """Verify a shared secret token in constant time; fail closed if secret is unconfigured."""
    expected = (expected_secret or "").strip()
    provided = (provided_token or "").strip()
    if not expected:
        raise SecurityAuthorizationError(
            "Endpoint secret token is not configured on host; failing closed."
        )
    if not provided or not hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8")):
        raise SecurityAuthorizationError("Invalid authentication token.")


def compute_hmac_signature(secret: str, timestamp: int | str, raw_body: bytes) -> str:
    """Compute hex HMAC-SHA256 over `<timestamp>.<raw_body>`."""
    clean_secret = secret.strip()
    if not clean_secret:
        raise ValueError("HMAC secret must not be empty.")
    mac = hmac.new(clean_secret.encode("utf-8"), digestmod=hashlib.sha256)
    mac.update(str(timestamp).encode("utf-8"))
    mac.update(b".")
    mac.update(raw_body)
    return mac.hexdigest()


def verify_timestamped_hmac_signature(
    *,
    secret: str | None,
    timestamp_header: str | None,
    signature_header: str | None,
    raw_body: bytes,
    max_age_seconds: int = 300,
    now_epoch: int | None = None,
) -> None:
    """Verify timestamp freshness and constant-time HMAC-SHA256 digest."""
    clean_secret = (secret or "").strip()
    if not clean_secret:
        raise SecurityAuthorizationError("HMAC secret is not configured; failing closed.")

    if not timestamp_header or not signature_header:
        raise SecurityAuthorizationError("Missing required HMAC timestamp or signature header.")

    try:
        ts_int = int(timestamp_header.strip())
    except ValueError as exc:
        raise SecurityAuthorizationError("Invalid HMAC timestamp header.") from exc

    reference_now = int(time.time()) if now_epoch is None else int(now_epoch)
    if abs(reference_now - ts_int) > max_age_seconds:
        raise SecurityAuthorizationError("HMAC signature timestamp expired or outside replay window.")

    provided_sig = signature_header.strip().lower()
    if provided_sig.startswith("sha256="):
        provided_sig = provided_sig[len("sha256=") :]

    expected_sig = compute_hmac_signature(clean_secret, ts_int, raw_body)
    if not hmac.compare_digest(provided_sig.encode("utf-8"), expected_sig.encode("utf-8")):
        raise SecurityAuthorizationError("HMAC signature verification failed.")
