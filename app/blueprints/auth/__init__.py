"""Operator authentication blueprint (`/api/v1/auth`) with persistent audit logging."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, session
from pydantic import BaseModel, Field, ValidationError

from app.config import enforce_financial_safety_locks
from app.core.exceptions import SecurityAuthorizationError
from app.core.security.auth_decorators import (
    SESSION_OPERATOR_ID_KEY,
    get_authenticated_operator,
    require_operator_auth,
)
from app.core.utilities.time import format_utc_iso
from app.repositories.audit_repository import AuditRepository
from app.repositories.operator_repository import OperatorRepository

auth_bp = Blueprint("auth_v1", __name__, url_prefix="/api/v1/auth")


class LoginRequestSchema(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


@auth_bp.post("/login")
def login():
    """Authenticate an operator and issue an HTTPOnly SameSite session cookie."""
    enforce_financial_safety_locks(current_app.config)

    raw_json = request.get_json(silent=True)
    if not isinstance(raw_json, dict):
        return (
            jsonify(
                {
                    "status": "error",
                    "error": {
                        "code": "invalid_payload",
                        "message": "Expected JSON object with username and password.",
                    },
                }
            ),
            400,
        )

    try:
        credentials = LoginRequestSchema.model_validate(raw_json)
    except ValidationError:
        return (
            jsonify(
                {
                    "status": "error",
                    "error": {
                        "code": "invalid_payload",
                        "message": "Username and password are required.",
                    },
                }
            ),
            400,
        )

    op_repo = OperatorRepository()
    audit_repo = AuditRepository()

    # Ensure optional env-configured bootstrap operator exists before lookup
    op_repo.ensure_bootstrap_operator(
        username=str(current_app.config.get("OPERATOR_USERNAME", "")),
        password_hash=str(current_app.config.get("OPERATOR_PASSWORD_HASH", "")),
    )

    operator = op_repo.get_by_username(credentials.username)
    client_ip = request.remote_addr

    if operator is None or not operator.is_active or not operator.verify_password(credentials.password):
        audit_repo.record_event(
            event_type="AUTH_LOGIN_FAILED",
            actor=credentials.username.strip(),
            severity="WARNING",
            resource_type="operator_session",
            ip_address=client_ip,
            details={"reason": "invalid_credentials_or_inactive"},
        )
        raise SecurityAuthorizationError("Invalid operator username or password.")

    session.clear()
    session[SESSION_OPERATOR_ID_KEY] = operator.id
    session.permanent = False
    op_repo.mark_logged_in(operator)

    audit_repo.record_event(
        event_type="AUTH_LOGIN_SUCCESS",
        actor=operator.username,
        severity="INFO",
        resource_type="operator_session",
        resource_id=str(operator.id),
        ip_address=client_ip,
        details={"trading_mode": current_app.config["TRADING_MODE"]},
    )

    return (
        jsonify(
            {
                "status": "ok",
                "operator": {
                    "id": operator.id,
                    "username": operator.username,
                    "last_login_at": format_utc_iso(operator.last_login_at)
                    if operator.last_login_at
                    else None,
                },
                "safety": {
                    "trading_mode": current_app.config["TRADING_MODE"],
                    "live_orders_enabled": bool(current_app.config["ALLOW_LIVE_NOBITEX_ORDERS"]),
                },
            }
        ),
        200,
    )


@auth_bp.post("/logout")
@require_operator_auth
def logout():
    """Terminate the active operator session and write an audit entry."""
    operator = get_authenticated_operator()
    assert operator is not None
    AuditRepository().record_event(
        event_type="AUTH_LOGOUT",
        actor=operator.username,
        severity="INFO",
        resource_type="operator_session",
        resource_id=str(operator.id),
        ip_address=request.remote_addr,
    )
    session.clear()
    return jsonify({"status": "ok"}), 200


@auth_bp.get("/me")
@require_operator_auth
def current_operator_profile():
    """Return current authenticated operator profile and active financial safety locks."""
    enforce_financial_safety_locks(current_app.config)
    operator = get_authenticated_operator()
    assert operator is not None
    return (
        jsonify(
            {
                "status": "ok",
                "operator": {
                    "id": operator.id,
                    "username": operator.username,
                    "last_login_at": format_utc_iso(operator.last_login_at)
                    if operator.last_login_at
                    else None,
                },
                "safety": {
                    "trading_mode": current_app.config["TRADING_MODE"],
                    "live_orders_enabled": bool(current_app.config["ALLOW_LIVE_NOBITEX_ORDERS"]),
                },
            }
        ),
        200,
    )
