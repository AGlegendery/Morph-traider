"""SQLAlchemy ORM models for shared-hosting cron locks and scheduled task state."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.utilities.time import utc_now
from app.extensions import db


class TaskLock(db.Model):
    """Database-backed expiring lease lock preventing overlapping cron worker executions."""

    __tablename__ = "task_locks"

    lock_name: Mapped[str] = mapped_column(String(96), primary_key=True)
    owner_run_id: Mapped[str] = mapped_column(String(96), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    locked_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ScheduledTaskState(db.Model):
    """Persistent cadence, heartbeat, failure, and missed-interval recovery state per job."""

    __tablename__ = "scheduled_task_states"

    task_name: Mapped[str] = mapped_column(String(96), primary_key=True)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str] = mapped_column(String(32), nullable=False, default="never_run")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missed_runs_recovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_run_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class TaskExecutionLog(db.Model):
    """Idempotent execution ledger for cron tick runs and individual periodic tasks."""

    __tablename__ = "task_execution_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    trigger_source: Mapped[str] = mapped_column(String(48), nullable=False, default="cron_http")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
