"""Tests for Task 1.1: Flask WSGI Factory, Financial Safety Locks, SQLite WAL & Health Probe."""

from __future__ import annotations

from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.core.exceptions import ConfigurationError, FinancialSafetyLockError
from app.extensions import db


def test_health_endpoint_reports_paper_mode_and_db_ok(client: FlaskClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    body = response.get_json()
    assert body is not None
    assert body["status"] == "ok"
    assert body["service"] == "morph-traider"
    assert body["environment"] == "testing"
    assert body["trading_mode"] == "paper"
    assert body["live_orders_enabled"] is False
    assert body["database"] == "ok"
    assert "T" in body["timestamp_utc"]


def test_sqlite_wal_and_foreign_keys_pragmas_enabled(app: Flask) -> None:
    with app.app_context():
        raw_conn = db.engine.raw_connection()
        try:
            cursor = raw_conn.cursor()
            cursor.execute("PRAGMA journal_mode;")
            journal_mode = cursor.fetchone()[0]
            cursor.execute("PRAGMA foreign_keys;")
            foreign_keys = cursor.fetchone()[0]
            cursor.execute("PRAGMA busy_timeout;")
            busy_timeout = cursor.fetchone()[0]
            cursor.close()
        finally:
            raw_conn.close()

    assert str(journal_mode).lower() == "wal"
    assert int(foreign_keys) == 1
    assert int(busy_timeout) == 5000


@pytest.mark.parametrize("forbidden_mode", ["live", "live_spot", "production", "real", ""])
def test_startup_rejects_any_non_paper_trading_mode(tmp_path: Path, forbidden_mode: str) -> None:
    with pytest.raises(FinancialSafetyLockError, match="TRADING_MODE"):
        create_app(
            {
                "ENV_NAME": "testing",
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'blocked.db'}",
                "TRADING_MODE": forbidden_mode,
                "ALLOW_LIVE_NOBITEX_ORDERS": False,
            }
        )


@pytest.mark.parametrize("truthy_flag", [True, "true", "1", "yes"])
def test_startup_rejects_live_nobitex_orders_flag(tmp_path: Path, truthy_flag: object) -> None:
    with pytest.raises(FinancialSafetyLockError, match="ALLOW_LIVE_NOBITEX_ORDERS"):
        create_app(
            {
                "ENV_NAME": "testing",
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'blocked_flag.db'}",
                "TRADING_MODE": "paper",
                "ALLOW_LIVE_NOBITEX_ORDERS": truthy_flag,
            }
        )


def test_production_env_rejects_missing_secret_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ConfigurationError, match="SECRET_KEY"):
        create_app(
            {
                "ENV_NAME": "production",
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'prod.db'}",
            }
        )


def test_wsgi_entrypoint_exposes_callable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FLASK_ENV", "testing")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'wsgi.db'}")
    monkeypatch.setenv("TRADING_MODE", "paper")
    monkeypatch.setenv("ALLOW_LIVE_NOBITEX_ORDERS", "false")

    import importlib
    import wsgi

    reloaded = importlib.reload(wsgi)
    assert callable(reloaded.application)
    assert reloaded.application.config["TRADING_MODE"] == "paper"
    assert reloaded.application.config["ALLOW_LIVE_NOBITEX_ORDERS"] is False
