"""Verify Flask-Migrate schema upgrade creates all Phase 1 tables cleanly."""

from __future__ import annotations

from pathlib import Path

from flask_migrate import upgrade
from sqlalchemy import inspect

from app import create_app
from app.extensions import db


def test_flask_migrate_upgrade_creates_all_phase_1_tables(tmp_path: Path) -> None:
    migrated_db_path = tmp_path / "migrated.db"
    flask_app = create_app(
        {
            "ENV_NAME": "testing",
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{migrated_db_path}",
            "TRADING_MODE": "paper",
            "ALLOW_LIVE_NOBITEX_ORDERS": False,
        }
    )
    migrations_dir = str(Path(__file__).resolve().parent.parent / "migrations")
    with flask_app.app_context():
        upgrade(directory=migrations_dir)
        with db.engine.connect() as conn:
            tables = set(inspect(conn).get_table_names())

    expected_tables = {
        "alembic_version",
        "audit_logs",
        "operator_users",
        "scheduled_task_states",
        "task_execution_logs",
        "task_locks",
    }
    assert expected_tables.issubset(tables)
