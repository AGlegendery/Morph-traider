"""Flask extensions and SQLite shared-hosting connection PRAGMA tuning."""

from __future__ import annotations

import sqlite3
from typing import Any

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Engine, event

db = SQLAlchemy()
migrate = Migrate()


@event.listens_for(Engine, "connect")
def _configure_sqlite_connection(dbapi_connection: Any, _connection_record: Any) -> None:
    """Apply safe concurrency and integrity PRAGMAs whenever connected to SQLite."""
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
    finally:
        cursor.close()
