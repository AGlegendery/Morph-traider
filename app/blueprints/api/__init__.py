"""Core `/api/v1` endpoints: health probe and HMAC/token-protected cron tick."""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import inspect

from app.config import enforce_financial_safety_locks
from app.core.security.hmac_auth import (
    verify_bearer_or_secret_token,
    verify_timestamped_hmac_signature,
)
from app.extensions import db
from app.tasks import build_default_task_orchestrator

api_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")


def _verify_cron_request_auth() -> None:
    """Authenticate shared-hosting cron caller via HMAC signature or shared token header."""
    cron_secret = str(current_app.config.get("CRON_SECRET_TOKEN", "")).strip()
    signature_header = request.headers.get("X-Cron-Signature")
    timestamp_header = request.headers.get("X-Cron-Timestamp")

    if signature_header or timestamp_header:
        verify_timestamped_hmac_signature(
            secret=cron_secret,
            timestamp_header=timestamp_header,
            signature_header=signature_header,
            raw_body=request.get_data(cache=True),
            max_age_seconds=int(current_app.config.get("CRON_SIGNATURE_MAX_AGE_SECONDS", 300)),
        )
        return

    token_header = request.headers.get("X-Cron-Token")
    verify_bearer_or_secret_token(token_header, cron_secret)


@api_bp.get("/health")
def health_check():
    """Lightweight liveness, DB connectivity, and financial safety status probe."""
    enforce_financial_safety_locks(current_app.config)

    db_status = "ok"
    http_status = 200
    try:
        with db.engine.connect() as conn:
            table_names = inspect(conn).get_table_names()
            if not isinstance(table_names, list):
                db_status = "degraded"
                http_status = 503
    except Exception:
        db.session.rollback()
        db_status = "degraded"
        http_status = 503

    payload = {
        "status": "ok" if http_status == 200 else "degraded",
        "service": current_app.config.get("SERVICE_NAME", "morph-traider"),
        "environment": current_app.config.get("ENV_NAME", "unknown"),
        "trading_mode": current_app.config["TRADING_MODE"],
        "live_orders_enabled": bool(current_app.config["ALLOW_LIVE_NOBITEX_ORDERS"]),
        "database": db_status,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    return jsonify(payload), http_status


@api_bp.post("/tasks/tick")
def trigger_cron_tick():
    """Shared-hosting cron entrypoint guarded by HMAC/token auth and SQL lease locks."""
    enforce_financial_safety_locks(current_app.config)
    _verify_cron_request_auth()

    idempotency_key = request.headers.get("Idempotency-Key")
    orchestrator = build_default_task_orchestrator()
    summary = orchestrator.run_tick(
        app_config=dict(current_app.config),
        trigger_source="cron_http",
        idempotency_key=idempotency_key,
    )
    http_code = 200 if summary["status"] in {"completed", "skipped_locked"} else 207
    return jsonify(summary), http_code
