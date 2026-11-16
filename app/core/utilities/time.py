"""Timezone-aware UTC clock helpers (never use naive datetimes)."""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    """Normalize a datetime to timezone-aware UTC (attaching UTC if SQLite returned naive)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def format_utc_iso(dt: datetime | None = None) -> str:
    """Format a datetime as an ISO-8601 UTC string."""
    target = ensure_utc(dt) if dt is not None else utc_now()
    return target.isoformat()
