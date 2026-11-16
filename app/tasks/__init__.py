"""Default periodic task registry (no background threads; invoked via cron tick)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from flask import current_app

from app.config import enforce_financial_safety_locks
from app.core.utilities.time import format_utc_iso
from app.services.task_orchestrator import TaskOrchestratorService


def system_heartbeat_task(tick_time: datetime) -> dict[str, Any]:
    """Baseline idempotent heartbeat verifying Paper-Trading safety lock on every cron tick."""
    enforce_financial_safety_locks(current_app.config)
    return {
        "heartbeat_utc": format_utc_iso(tick_time),
        "trading_mode": current_app.config["TRADING_MODE"],
        "live_orders_enabled": bool(current_app.config["ALLOW_LIVE_NOBITEX_ORDERS"]),
    }


def build_default_task_orchestrator() -> TaskOrchestratorService:
    """Create the application task orchestrator populated with registered periodic jobs."""
    orchestrator = TaskOrchestratorService()
    orchestrator.register_task(
        "system_heartbeat",
        interval_seconds=60,
        handler=system_heartbeat_task,
    )
    return orchestrator
