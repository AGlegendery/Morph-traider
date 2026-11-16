"""Tests for Task 1.3: SQL Lease Locks, Idempotent TaskOrchestrator & `/api/v1/tasks/tick`."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.core.security.hmac_auth import compute_hmac_signature
from app.extensions import db
from app.models.tasks import ScheduledTaskState, TaskLock
from app.repositories.task_repository import TaskRepository
from app.services.task_orchestrator import GLOBAL_TICK_LOCK_NAME, TaskOrchestratorService


@pytest.fixture()
def cron_secret() -> str:
    return "unit-test-cron-hmac-key-32-characters-long"


@pytest.fixture()
def cron_app(tmp_path: Path, cron_secret: str) -> Iterator[Flask]:
    db_path = tmp_path / "cron_test.db"
    flask_app = create_app(
        {
            "ENV_NAME": "testing",
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
            "TRADING_MODE": "paper",
            "ALLOW_LIVE_NOBITEX_ORDERS": False,
            "CRON_SECRET_TOKEN": cron_secret,
        }
    )
    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def cron_client(cron_app: Flask) -> FlaskClient:
    return cron_app.test_client()


def test_cron_tick_rejects_missing_or_invalid_credentials(cron_client: FlaskClient) -> None:
    unauthenticated = cron_client.post("/api/v1/tasks/tick")
    assert unauthenticated.status_code == 403
    assert unauthenticated.get_json()["error"]["code"] == "authorization_failed"

    wrong_token = cron_client.post(
        "/api/v1/tasks/tick",
        headers={"X-Cron-Token": "wrong-value"},
    )
    assert wrong_token.status_code == 403


def test_cron_tick_accepts_signed_hmac_and_idempotent_replay(
    cron_client: FlaskClient, cron_secret: str
) -> None:
    raw_body = b""
    now_ts = str(int(time.time()))
    sig = compute_hmac_signature(cron_secret, now_ts, raw_body)

    headers = {
        "X-Cron-Timestamp": now_ts,
        "X-Cron-Signature": f"sha256={sig}",
        "Idempotency-Key": "cron-minute-2026-11-16T09:00Z",
    }
    first = cron_client.post("/api/v1/tasks/tick", data=raw_body, headers=headers)
    assert first.status_code == 200
    first_json = first.get_json()
    assert first_json["status"] == "completed"
    assert first_json["replayed_idempotent"] is False
    assert len(first_json["executed_tasks"]) == 1
    assert first_json["executed_tasks"][0]["task_name"] == "system_heartbeat"

    # Replaying identical Idempotency-Key returns prior result without re-executing tasks
    replay = cron_client.post("/api/v1/tasks/tick", data=raw_body, headers=headers)
    assert replay.status_code == 200
    replay_json = replay.get_json()
    assert replay_json["run_id"] == first_json["run_id"]
    assert replay_json["replayed_idempotent"] is True


def test_sql_lease_lock_skips_concurrent_worker_and_recovers_after_crash(
    cron_app: Flask,
) -> None:
    t0 = datetime(2026, 11, 16, 10, 0, 0, tzinfo=timezone.utc)
    repo = TaskRepository()

    with cron_app.app_context():
        # Simulate Worker A acquiring lease and holding it until t0 + 55s
        assert repo.try_acquire_lease(
            lock_name=GLOBAL_TICK_LOCK_NAME,
            owner_run_id="crashed_worker_a",
            lease_seconds=55,
            now=t0,
        )

        orchestrator = TaskOrchestratorService(repository=repo)
        orchestrator.register_task(
            "sample_job",
            interval_seconds=60,
            handler=lambda ts: {"ran_at": ts.isoformat()},
        )

        # At t0 + 10s, Worker B triggers cron tick -> cleanly skipped because lease is active
        contended = orchestrator.run_tick(
            app_config=dict(cron_app.config),
            now=t0 + timedelta(seconds=10),
        )
        assert contended["status"] == "skipped_locked"

        # Worker A crashed without releasing lock; at t0 + 60s lease has expired -> Worker C recovers!
        recovered = orchestrator.run_tick(
            app_config=dict(cron_app.config),
            now=t0 + timedelta(seconds=60),
        )
        assert recovered["status"] == "completed"
        assert recovered["executed_tasks"][0]["task_name"] == "sample_job"
        # Lease was cleanly released after completion
        assert db.session.get(TaskLock, GLOBAL_TICK_LOCK_NAME) is None


def test_missed_cron_intervals_are_detected_and_counted_on_recovery(
    cron_app: Flask,
) -> None:
    t0 = datetime(2026, 11, 16, 12, 0, 0, tzinfo=timezone.utc)

    with cron_app.app_context():
        orchestrator = TaskOrchestratorService()
        orchestrator.register_task(
            "minute_sync",
            interval_seconds=60,
            handler=lambda ts: {"ok": True},
        )

        # Initial run at 12:00
        res1 = orchestrator.run_tick(app_config=dict(cron_app.config), now=t0)
        assert res1["executed_tasks"][0]["missed_intervals_recovered"] == 0

        # Early trigger at 12:00:30 -> skipped as not yet due
        res_early = orchestrator.run_tick(
            app_config=dict(cron_app.config),
            now=t0 + timedelta(seconds=30),
        )
        assert res_early["skipped_not_due"] == ["minute_sync"]

        # Host downtime until 12:05:00 (5 minutes elapsed -> 4 missed 1-min intervals recovered)
        res_catchup = orchestrator.run_tick(
            app_config=dict(cron_app.config),
            now=t0 + timedelta(minutes=5),
        )
        assert res_catchup["executed_tasks"][0]["missed_intervals_recovered"] == 4

        state = db.session.get(ScheduledTaskState, "minute_sync")
        assert state is not None
        assert state.missed_runs_recovered == 4
        assert state.last_status == "ok"
