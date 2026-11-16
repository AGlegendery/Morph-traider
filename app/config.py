"""Typed application configuration and hard Paper-Trading safety lock enforcement."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any, Mapping

from app.core.exceptions import ConfigurationError, FinancialSafetyLockError


def _parse_bool_env(raw_value: str | bool | None, *, default: bool = False) -> bool:
    if isinstance(raw_value, bool):
        return raw_value
    if raw_value is None:
        return default
    normalized = str(raw_value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    raise ConfigurationError(f"Invalid boolean configuration value: {raw_value!r}")


class BaseConfig:
    """Shared baseline configuration safe for WSGI shared hosting."""

    SERVICE_NAME: str = "morph-traider"
    ENV_NAME: str = "production"
    DEBUG: bool = False
    TESTING: bool = False

    # Session & Cookie Security (loaded from environment; ephemeral fallback in dev/test only)
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"
    SESSION_COOKIE_SECURE: bool = True

    # Financial Safety Locks (HARD-LOCKED TO PAPER TRADING IN PHASES 0-8)
    TRADING_MODE: str = "paper"
    ALLOW_LIVE_NOBITEX_ORDERS: bool = False

    # SQLAlchemy Settings
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_DATABASE_URI: str = ""

    # Shared-Hosting Cron & Task Runner Budgets
    CRON_MAX_EXECUTION_SECONDS: int = 20
    CRON_SIGNATURE_MAX_AGE_SECONDS: int = 300


class DevelopmentConfig(BaseConfig):
    ENV_NAME = "development"
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class TestingConfig(BaseConfig):
    ENV_NAME = "testing"
    TESTING = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(BaseConfig):
    ENV_NAME = "production"
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True


CONFIG_BY_ENV: dict[str, type[BaseConfig]] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def build_config_dict(
    instance_path: Path,
    config_override: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble validated configuration dictionary from environment + explicit overrides."""
    overrides = dict(config_override or {})
    env_name = str(
        overrides.get("ENV_NAME")
        or os.environ.get("FLASK_ENV")
        or "development"
    ).strip().lower()

    config_cls = CONFIG_BY_ENV.get(env_name)
    if config_cls is None:
        raise ConfigurationError(
            f"Unsupported FLASK_ENV / ENV_NAME {env_name!r}; expected one of {sorted(CONFIG_BY_ENV)}."
        )

    cfg: dict[str, Any] = {
        key: getattr(config_cls, key)
        for key in dir(config_cls)
        if key.isupper()
    }

    env_secret_key = os.environ.get("SECRET_KEY", "").strip()
    cfg["SECRET_KEY"] = env_secret_key
    cfg["CRON_SECRET_TOKEN"] = os.environ.get("CRON_SECRET_TOKEN", "").strip()
    cfg["OPERATOR_USERNAME"] = os.environ.get("OPERATOR_USERNAME", "").strip()
    cfg["OPERATOR_PASSWORD_HASH"] = os.environ.get("OPERATOR_PASSWORD_HASH", "").strip()

    if "TRADING_MODE" in os.environ:
        cfg["TRADING_MODE"] = os.environ["TRADING_MODE"]
    if "ALLOW_LIVE_NOBITEX_ORDERS" in os.environ:
        cfg["ALLOW_LIVE_NOBITEX_ORDERS"] = _parse_bool_env(
            os.environ["ALLOW_LIVE_NOBITEX_ORDERS"], default=False
        )
    if (
        "CRON_MAX_EXECUTION_SECONDS" in os.environ
        and os.environ["CRON_MAX_EXECUTION_SECONDS"].strip()
    ):
        cfg["CRON_MAX_EXECUTION_SECONDS"] = int(os.environ["CRON_MAX_EXECUTION_SECONDS"])

    default_sqlite_path = instance_path / "morph_traider.db"
    env_db_url = os.environ.get("DATABASE_URL", "").strip()
    cfg["SQLALCHEMY_DATABASE_URI"] = env_db_url or f"sqlite:///{default_sqlite_path}"

    # Apply explicit overrides last (used by tests or programmatic callers)
    cfg.update(overrides)

    # Require explicit strong SECRET_KEY in production; generate ephemeral random key in dev/test
    final_secret = str(cfg.get("SECRET_KEY", "")).strip()
    if cfg["ENV_NAME"] == "production":
        if len(final_secret) < 16:
            raise ConfigurationError(
                "Production environment requires an explicit SECRET_KEY (>=16 chars) from environment."
            )
    elif not final_secret:
        cfg["SECRET_KEY"] = secrets.token_hex(32)

    cfg["ALLOW_LIVE_NOBITEX_ORDERS"] = _parse_bool_env(
        cfg.get("ALLOW_LIVE_NOBITEX_ORDERS"), default=False
    )
    cfg["TRADING_MODE"] = str(cfg.get("TRADING_MODE", "")).strip().lower()

    enforce_financial_safety_locks(cfg)
    return cfg


def enforce_financial_safety_locks(config: Mapping[str, Any]) -> None:
    """Unconditionally enforce Paper-Trading-Only locks at startup and runtime."""
    trading_mode = str(config.get("TRADING_MODE", "")).strip().lower()
    live_orders_flag = bool(config.get("ALLOW_LIVE_NOBITEX_ORDERS", False))

    if trading_mode != "paper":
        raise FinancialSafetyLockError(
            f"Financial safety lock triggered: TRADING_MODE={trading_mode!r} is forbidden. "
            "Morph-Traider is strictly locked to TRADING_MODE='paper'."
        )

    if live_orders_flag is not False:
        raise FinancialSafetyLockError(
            "Financial safety lock triggered: ALLOW_LIVE_NOBITEX_ORDERS=True is forbidden. "
            "Live Nobitex order submission is disabled by charter."
        )
