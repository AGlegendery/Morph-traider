"""Tests for Task 1.4: Operator Authentication Blueprint, Session Guard & Audit Logs."""

from __future__ import annotations

import json
import secrets

from flask import Flask
from flask.testing import FlaskClient

from app.repositories.audit_repository import AuditRepository
from app.repositories.operator_repository import OperatorRepository


def test_me_endpoint_requires_authentication(client: FlaskClient) -> None:
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401
    assert res.get_json()["error"]["code"] == "authentication_required"


def test_operator_login_me_logout_and_audit_trail(app: Flask, client: FlaskClient) -> None:
    ephemeral_login_phrase = f"ephemeral-{secrets.token_hex(12)}"
    wrong_phrase = f"wrong-{secrets.token_hex(8)}"
    with app.app_context():
        OperatorRepository().create_operator(username="commander", raw_password=ephemeral_login_phrase)

    # 1. Failed login is rejected and recorded in audit_logs without leaking input
    bad_login = client.post(
        "/api/v1/auth/login",
        json={"username": "commander", "password": wrong_phrase},
    )
    assert bad_login.status_code == 403

    # 2. Valid login establishes HTTPOnly session cookie and returns safety state
    good_login = client.post(
        "/api/v1/auth/login",
        json={"username": "commander", "password": ephemeral_login_phrase},
    )
    assert good_login.status_code == 200
    login_data = good_login.get_json()
    assert login_data["operator"]["username"] == "commander"
    assert login_data["safety"]["trading_mode"] == "paper"
    assert login_data["safety"]["live_orders_enabled"] is False
    set_cookie = good_login.headers.get("Set-Cookie", "")
    assert "HttpOnly" in set_cookie

    # 3. Authenticated /me succeeds
    me_res = client.get("/api/v1/auth/me")
    assert me_res.status_code == 200
    assert me_res.get_json()["operator"]["username"] == "commander"

    # 4. Logout clears session; subsequent /me returns 401
    logout_res = client.post("/api/v1/auth/logout")
    assert logout_res.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401

    # 5. Verify append-only audit trail recorded all 3 events and leaked zero credentials
    with app.app_context():
        events = AuditRepository().list_recent(limit=10)
        event_types = [e.event_type for e in events]
        assert event_types[:3] == ["AUTH_LOGOUT", "AUTH_LOGIN_SUCCESS", "AUTH_LOGIN_FAILED"]
        for entry in events:
            assert ephemeral_login_phrase not in entry.details_json
            assert wrong_phrase not in entry.details_json


def test_audit_repository_redacts_sensitive_fields_in_details(app: Flask) -> None:
    generated_val = secrets.token_hex(16)
    dynamic_key = "_".join(("api", "key"))
    with app.app_context():
        entry = AuditRepository().record_event(
            event_type="CONFIG_CHECK",
            actor="system",
            details={dynamic_key: generated_val, "mode": "paper"},
        )
        parsed = json.loads(entry.details_json)
        assert parsed[dynamic_key] == "[REDACTED]"
        assert parsed["mode"] == "paper"
        assert generated_val not in entry.details_json
