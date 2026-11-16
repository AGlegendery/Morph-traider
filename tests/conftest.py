"""Shared pytest fixtures for Morph-Traider backend test suites."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.extensions import db


@pytest.fixture()
def app(tmp_path: Path) -> Iterator[Flask]:
    """Create an isolated Flask application backed by a temporary file SQLite database."""
    db_path = tmp_path / "test_morph_traider.db"
    flask_app = create_app(
        {
            "ENV_NAME": "testing",
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
            "TRADING_MODE": "paper",
            "ALLOW_LIVE_NOBITEX_ORDERS": False,
        }
    )
    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    """Return a Flask test client bound to the isolated app fixture."""
    return app.test_client()
