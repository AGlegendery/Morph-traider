"""Tests for Task 1.2: Exact Decimal/RLS-IRT Math, UTC Clock, Idempotency, HMAC & Log Redaction."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.core.exceptions import (
    CurrencyUnitMismatchError,
    InvalidMonetaryValueError,
    SecurityAuthorizationError,
)
from app.core.logging import (
    REDACTED_PLACEHOLDER,
    StructuredRedactingFormatter,
    redact_sensitive_data,
)
from app.core.security.hmac_auth import (
    compute_hmac_signature,
    verify_bearer_or_secret_token,
    verify_timestamped_hmac_signature,
)
from app.core.utilities.idempotency import derive_idempotency_key
from app.core.utilities.money import (
    CurrencyUnit,
    MoneyAmount,
    irt_to_rls,
    parse_exact_decimal,
    rls_to_irt,
)
from app.core.utilities.time import ensure_utc, format_utc_iso, utc_now


def test_rls_and_irt_exact_10_to_1_conversion() -> None:
    assert rls_to_irt("65000000000") == Decimal("6500000000")
    assert irt_to_rls("6500000000") == Decimal("65000000000")

    rls_price = MoneyAmount("123450", CurrencyUnit.RLS)
    irt_price = rls_price.to_irt()
    assert irt_price.unit == CurrencyUnit.IRT
    assert irt_price.amount == Decimal("12345")
    assert irt_price.to_rls() == rls_price


def test_money_rejects_binary_float_and_non_finite_values() -> None:
    with pytest.raises(InvalidMonetaryValueError):
        parse_exact_decimal(0.1)  # type: ignore[arg-type]

    with pytest.raises(InvalidMonetaryValueError):
        MoneyAmount(True, CurrencyUnit.USDT)  # type: ignore[arg-type]

    with pytest.raises(InvalidMonetaryValueError):
        MoneyAmount("NaN", CurrencyUnit.USDT)


def test_money_blocks_cross_unit_addition_and_crypto_symbol_mismatch() -> None:
    rls = MoneyAmount("1000", CurrencyUnit.RLS)
    irt = MoneyAmount("100", CurrencyUnit.IRT)
    with pytest.raises(CurrencyUnitMismatchError):
        _ = rls + irt

    btc = MoneyAmount("0.05", CurrencyUnit.CRYPTO, asset_symbol="BTC")
    eth = MoneyAmount("0.05", CurrencyUnit.CRYPTO, asset_symbol="ETH")
    with pytest.raises(CurrencyUnitMismatchError):
        _ = btc + eth

    combined_btc = btc + MoneyAmount("0.025", CurrencyUnit.CRYPTO, asset_symbol="btc")
    assert combined_btc.amount == Decimal("0.075")
    assert combined_btc.asset_symbol == "BTC"


def test_money_quantize_down_floors_safely_for_order_lots() -> None:
    qty = MoneyAmount("0.123459", CurrencyUnit.CRYPTO, asset_symbol="BTC")
    floored = qty.quantize_down("0.0001")
    assert floored.amount == Decimal("0.1234")


def test_utc_clock_helpers_normalize_naive_and_offset_datetimes() -> None:
    now = utc_now()
    assert now.tzinfo == timezone.utc

    naive = datetime(2026, 11, 16, 12, 0, 0)
    normalized = ensure_utc(naive)
    assert normalized.tzinfo == timezone.utc

    tehran_tz = timezone(timedelta(hours=3, minutes=30))
    local_dt = datetime(2026, 11, 16, 15, 30, 0, tzinfo=tehran_tz)
    assert ensure_utc(local_dt).hour == 12
    assert format_utc_iso(local_dt).endswith("+00:00")


def test_idempotency_key_is_deterministic_across_dict_key_order() -> None:
    k1 = derive_idempotency_key("signal", {"symbol": "BTCIRT", "side": "BUY", "price": "100"})
    k2 = derive_idempotency_key("signal", {"price": "100", "symbol": "BTCIRT", "side": "BUY"})
    k3 = derive_idempotency_key("signal", {"price": "101", "symbol": "BTCIRT", "side": "BUY"})
    assert k1 == k2
    assert len(k1) == 64
    assert k1 != k3


def test_hmac_verification_and_replay_protection() -> None:
    secret_val = "test-webhook-signing-key"
    body = b'{"symbol":"BTCIRT","action":"BUY"}'
    ts = 1763294400
    sig = compute_hmac_signature(secret_val, ts, body)

    verify_timestamped_hmac_signature(
        secret=secret_val,
        timestamp_header=str(ts),
        signature_header=f"sha256={sig}",
        raw_body=body,
        max_age_seconds=300,
        now_epoch=ts + 60,
    )

    # Expired replay rejected
    with pytest.raises(SecurityAuthorizationError, match="expired"):
        verify_timestamped_hmac_signature(
            secret=secret_val,
            timestamp_header=str(ts),
            signature_header=sig,
            raw_body=body,
            max_age_seconds=300,
            now_epoch=ts + 600,
        )

    # Tampered body rejected
    with pytest.raises(SecurityAuthorizationError, match="verification failed"):
        verify_timestamped_hmac_signature(
            secret=secret_val,
            timestamp_header=str(ts),
            signature_header=sig,
            raw_body=b'{"symbol":"BTCIRT","action":"SELL"}',
            max_age_seconds=300,
            now_epoch=ts + 10,
        )

    # Empty secret fails closed
    with pytest.raises(SecurityAuthorizationError):
        verify_bearer_or_secret_token("anything", "")


def test_structured_logger_redacts_secrets_and_tokens() -> None:
    raw = {
        "symbol": "BTCIRT",
        "Authorization": "Token sensitive-nobitex-value",
        "nested": {"cron_secret_token": "abc", "safe_count": 3},
    }
    redacted = redact_sensitive_data(raw)
    assert redacted["Authorization"] == REDACTED_PLACEHOLDER
    assert redacted["nested"]["cron_secret_token"] == REDACTED_PLACEHOLDER
    assert redacted["nested"]["safe_count"] == 3

    record = logging.LogRecord(
        name="morph.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="checked headers",
        args=(),
        exc_info=None,
    )
    record.context = raw
    formatted = json.loads(StructuredRedactingFormatter().format(record))
    assert formatted["context"]["Authorization"] == REDACTED_PLACEHOLDER
    assert "sensitive-nobitex-value" not in json.dumps(formatted)
