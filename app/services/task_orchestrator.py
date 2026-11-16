"""Transport-agnostic, shared-hosting-safe periodic task orchestrator."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from app.config import enforce_financial_safety_locks
from app.core.utilities.time import ensure_utc, format_utc_iso, utc_now
from app.extensions import db
from app.repositories.task_repository import TaskRepository

TaskHandler = Callable[[datetime], dict[str, Any]]
GLOBAL_TICK_LOCK_NAME = "morph_traider_cron_tick"


@dataclass(frozen=True, slots=True)
class RegisteredTaskSpec:
    name: str
    interval_seconds: int
    handler: TaskHandler


class TaskOrchestratorService:
    """Executes due periodic tasks under SQL lease locks and strict WSGI time budgets."""

    def __init__(
        self,
        *,
        repository: TaskRepository | None = None,
        tasks: list[RegisteredTaskSpec] | None = None,
    ) -> None:
        self._repo = repository or TaskRepository()
        self._tasks: list[RegisteredTaskSpec] = list(tasks or [])

    def register_task(self, name: str, *, interval_seconds: int, handler: TaskHandler) -> None:
        if interval_seconds < 1:
            raise ValueError("interval_seconds must be >= 1.")
        self._tasks.append(
            RegisteredTaskSpec(name=name, interval_seconds=interval_seconds, handler=handler)
        )

    def run_tick(
        self,
        *,
        app_config: dict[str, Any],
        trigger_source: str = "cron_http",
        idempotency_key: str | None = None,
        lease_seconds: int = 55,
        max_execution_seconds: int | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Run one bounded, idempotent cron tick cycle."""
        enforce_financial_safety_locks(app_config)

        started_at = ensure_utc(now) if now is not None else utc_now()
        run_id = f"tick_{uuid.uuid4().hex[:16]}"
        effective_idem_key = (idempotency_key or "").strip() or run_id

        # 1. Idempotency replay short-circuit
        prior_log = self._repo.get_execution_by_idempotency_key(effective_idem_key)
        if prior_log is not None:
            cached_summary = json.loads(prior_log.summary_json)
            cached_summary["replayed_idempotent"] = True
            return cached_summary

        # 2. Acquire database-backed lease lock
        acquired = self._repo.try_acquire_lease(
            lock_name=GLOBAL_TICK_LOCK_NAME,
            owner_run_id=run_id,
            lease_seconds=lease_seconds,
            now=started_at,
        )
        if not acquired:
            return {
                "status": "skipped_locked",
                "run_id": run_id,
                "trading_mode": app_config["TRADING_MODE"],
                "timestamp_utc": format_utc_iso(started_at),
                "replayed_idempotent": False,
            }

        budget_seconds = (
            max_execution_seconds
            if max_execution_seconds is not None
            else int(app_config.get("CRON_MAX_EXECUTION_SECONDS", 20))
        )
        monotonic_deadline = time.monotonic() + max(1, budget_seconds)

        executed_tasks: list[dict[str, Any]] = []
        skipped_not_due: list[str] = []
        deferred_budget: list[str] = []
        overall_status = "completed"

        try:
            for spec in self._tasks:
                if time.monotonic() >= monotonic_deadline:
                    deferred_budget.append(spec.name)
                    continue

                state = self._repo.get_or_create_task_state(
                    task_name=spec.name,
                    interval_seconds=spec.interval_seconds,
                    now=started_at,
                )
                if not state.is_enabled:
                    skipped_not_due.append(spec.name)
                    continue

                missed_intervals = 0
                if state.last_completed_at is not None:
                    elapsed = (started_at - ensure_utc(state.last_completed_at)).total_seconds()
                    if elapsed < spec.interval_seconds:
                        skipped_not_due.append(spec.name)
                        continue
                    missed_intervals = max(0, int(elapsed // spec.interval_seconds) - 1)

                state.last_started_at = started_at
                state.last_run_id = run_id
                db.session.commit()

                try:
                    result_meta = spec.handler(started_at)
                    state.last_completed_at = ensure_utc(now) if now is not None else utc_now()
                    state.last_status = "ok"
                    state.last_error = None
                    state.consecutive_failures = 0
                    state.missed_runs_recovered += missed_intervals
                    state.updated_at = state.last_completed_at
                    db.session.commit()
                    executed_tasks.append(
                        {
                            "task_name": spec.name,
                            "status": "ok",
                            "missed_intervals_recovered": missed_intervals,
                            "details": result_meta,
                        }
                    )
                except Exception as exc:
                    db.session.rollback()
                    err_state = self._repo.get_or_create_task_state(
                        task_name=spec.name,
                        interval_seconds=spec.interval_seconds,
                        now=started_at,
                    )
                    err_state.last_status = "failed"
                    err_state.last_error = f"{type(exc).__name__}: {exc}"
                    err_state.consecutive_failures += 1
                    err_state.last_run_id = run_id
                    err_state.updated_at = utc_now()
                    db.session.commit()
                    overall_status = "partial_failure"
                    executed_tasks.append(
                        {
                            "task_name": spec.name,
                            "status": "failed",
                            "error": err_state.last_error,
                        }
                    )

            finished_at = ensure_utc(now) if now is not None else utc_now()
            summary: dict[str, Any] = {
                "status": overall_status,
                "run_id": run_id,
                "trigger_source": trigger_source,
                "trading_mode": app_config["TRADING_MODE"],
                "executed_tasks": executed_tasks,
                "skipped_not_due": skipped_not_due,
                "deferred_budget": deferred_budget,
                "timestamp_utc": format_utc_iso(finished_at),
                "replayed_idempotent": False,
            }
            self._repo.record_tick_execution(
                idempotency_key=effective_idem_key,
                run_id=run_id,
                trigger_source=trigger_source,
                started_at=started_at,
                finished_at=finished_at,
                status=overall_status,
                summary=summary,
            )
            return summary
        finally:
            self._repo.release_lease(lock_name=GLOBAL_TICK_LOCK_NAME, owner_run_id=run_id)
