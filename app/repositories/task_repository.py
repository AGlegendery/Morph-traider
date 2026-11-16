"""Repository for atomic SQL task lease locks, task states, and idempotent tick logs."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.core.utilities.time import ensure_utc, utc_now
from app.extensions import db
from app.models.tasks import ScheduledTaskState, TaskExecutionLog, TaskLock


class TaskRepository:
    """SQLite/PostgreSQL-portable ORM persistence operations for cron orchestration."""

    def get_execution_by_idempotency_key(self, idempotency_key: str) -> TaskExecutionLog | None:
        return (
            db.session.query(TaskExecutionLog)
            .filter_by(idempotency_key=idempotency_key)
            .one_or_none()
        )

    def try_acquire_lease(
        self,
        *,
        lock_name: str,
        owner_run_id: str,
        lease_seconds: int,
        now: datetime | None = None,
    ) -> bool:
        """Atomically acquire or take over an expired lease without in-memory locks."""
        current_time = ensure_utc(now) if now is not None else utc_now()
        expires_at = current_time + timedelta(seconds=max(1, lease_seconds))

        # 1. Atomically take over an expired lease via ORM synchronize_session=False update
        updated_rows = (
            db.session.query(TaskLock)
            .filter(
                TaskLock.lock_name == lock_name,
                TaskLock.locked_until <= current_time,
            )
            .update(
                {
                    TaskLock.owner_run_id: owner_run_id,
                    TaskLock.acquired_at: current_time,
                    TaskLock.locked_until: expires_at,
                    TaskLock.updated_at: current_time,
                },
                synchronize_session=False,
            )
        )
        if updated_rows == 1:
            db.session.commit()
            return True

        # 2. Check if an unexpired row currently holds the lease
        existing = db.session.get(TaskLock, lock_name)
        if existing is not None and ensure_utc(existing.locked_until) > current_time:
            db.session.rollback()
            return False

        # 3. Insert fresh lease row (race-guarded by primary key uniqueness)
        new_lock = TaskLock(
            lock_name=lock_name,
            owner_run_id=owner_run_id,
            acquired_at=current_time,
            locked_until=expires_at,
            updated_at=current_time,
        )
        db.session.add(new_lock)
        try:
            db.session.commit()
            return True
        except IntegrityError:
            db.session.rollback()
            return False

    def release_lease(self, *, lock_name: str, owner_run_id: str) -> None:
        """Release lease only if still owned by this run_id."""
        (
            db.session.query(TaskLock)
            .filter_by(lock_name=lock_name, owner_run_id=owner_run_id)
            .delete(synchronize_session=False)
        )
        db.session.commit()

    def get_or_create_task_state(
        self,
        *,
        task_name: str,
        interval_seconds: int,
        now: datetime | None = None,
    ) -> ScheduledTaskState:
        current_time = ensure_utc(now) if now is not None else utc_now()
        state = db.session.get(ScheduledTaskState, task_name)
        if state is None:
            state = ScheduledTaskState(
                task_name=task_name,
                interval_seconds=interval_seconds,
                is_enabled=True,
                last_status="never_run",
                consecutive_failures=0,
                missed_runs_recovered=0,
                updated_at=current_time,
            )
            db.session.add(state)
            db.session.flush()
        elif state.interval_seconds != interval_seconds:
            state.interval_seconds = interval_seconds
        return state

    def record_tick_execution(
        self,
        *,
        idempotency_key: str,
        run_id: str,
        trigger_source: str,
        started_at: datetime,
        finished_at: datetime,
        status: str,
        summary: dict[str, Any],
    ) -> TaskExecutionLog:
        duration_ms = max(
            0, int((ensure_utc(finished_at) - ensure_utc(started_at)).total_seconds() * 1000)
        )
        entry = TaskExecutionLog(
            idempotency_key=idempotency_key,
            run_id=run_id,
            trigger_source=trigger_source,
            started_at=ensure_utc(started_at),
            finished_at=ensure_utc(finished_at),
            duration_ms=duration_ms,
            status=status,
            summary_json=json.dumps(summary, default=str, ensure_ascii=True),
        )
        db.session.add(entry)
        db.session.commit()
        return entry
