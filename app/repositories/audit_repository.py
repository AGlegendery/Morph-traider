"""Repository for append-only AuditLog entries with automatic sensitive-key redaction."""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.core.logging import redact_sensitive_data
from app.core.utilities.time import utc_now
from app.extensions import db
from app.models.audit import AuditLog


class AuditRepository:
    """Append-only repository for security and trading governance events."""

    def record_event(
        self,
        *,
        event_type: str,
        actor: str = "system",
        severity: str = "INFO",
        resource_type: str | None = None,
        resource_id: str | None = None,
        ip_address: str | None = None,
        details: Mapping[str, Any] | None = None,
        commit: bool = True,
    ) -> AuditLog:
        sanitized_details = redact_sensitive_data(dict(details or {}))
        entry = AuditLog(
            event_type=event_type.strip().upper(),
            severity=severity.strip().upper(),
            actor=actor.strip() or "system",
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            details_json=json.dumps(sanitized_details, default=str, ensure_ascii=True),
            created_at=utc_now(),
        )
        db.session.add(entry)
        if commit:
            db.session.commit()
        else:
            db.session.flush()
        return entry

    def list_recent(self, *, limit: int = 50) -> list[AuditLog]:
        bounded_limit = max(1, min(limit, 500))
        return (
            db.session.query(AuditLog)
            .order_by(AuditLog.id.desc())
            .limit(bounded_limit)
            .all()
        )
