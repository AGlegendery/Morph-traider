"""Morph-Traider Flask WSGI Application Factory."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from dotenv import load_dotenv
from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from app.blueprints.api import api_bp
from app.blueprints.auth import auth_bp
from app.config import build_config_dict, enforce_financial_safety_locks
from app.core.exceptions import MorphTraiderError
from app.core.logging import configure_app_logging
from app.extensions import db, migrate
from app import models as _models  # noqa: F401 — register SQLAlchemy metadata for Flask-Migrate


def create_app(config_override: Mapping[str, Any] | None = None) -> Flask:
    """Construct and configure the modular Flask monolith."""
    load_dotenv(override=False)

    app = Flask(__name__, instance_relative_config=True)
    configure_app_logging(app.logger)
    instance_dir = Path(app.instance_path)
    instance_dir.mkdir(parents=True, exist_ok=True)

    validated_config = build_config_dict(instance_dir, config_override=config_override)
    app.config.from_mapping(validated_config)

    # Re-verify hard paper-trading lock on final mapped app.config
    enforce_financial_safety_locks(app.config)

    db.init_app(app)
    migrate.init_app(app, db)

    _register_error_handlers(app)
    _register_blueprints(app)

    return app


def _register_blueprints(app: Flask) -> None:
    app.register_blueprint(api_bp)
    app.register_blueprint(auth_bp)


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(MorphTraiderError)
    def handle_domain_error(exc: MorphTraiderError):
        return (
            jsonify(
                {
                    "status": "error",
                    "error": {
                        "code": exc.error_code,
                        "message": exc.message,
                    },
                }
            ),
            exc.status_code,
        )

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException):
        return (
            jsonify(
                {
                    "status": "error",
                    "error": {
                        "code": exc.name.lower().replace(" ", "_"),
                        "message": exc.description,
                    },
                }
            ),
            exc.code or 500,
        )
