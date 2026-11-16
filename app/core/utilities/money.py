"""Exact Decimal monetary math and Nobitex RLS <-> IRT unit safety guards."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP
from enum import StrEnum

from app.core.exceptions import CurrencyUnitMismatchError, InvalidMonetaryValueError

RLS_PER_IRT = Decimal("10")


class CurrencyUnit(StrEnum):
    """Canonical currency units used across Nobitex and Morph-Traider ledgers."""

    RLS = "RLS"      # Iranian Rial (Nobitex raw fiat unit: 10 RLS == 1 IRT)
    IRT = "IRT"      # Iranian Toman (1 IRT == 10 RLS)
    USDT = "USDT"    # Tether USD
    CRYPTO = "CRYPTO"  # Base crypto asset quantity (paired with asset_symbol)


def parse_exact_decimal(value: str | int | Decimal) -> Decimal:
    """Convert string, int, or Decimal to exact finite Decimal; reject binary floats outright."""
    if isinstance(value, bool) or isinstance(value, float):
        raise InvalidMonetaryValueError(
            f"Binary float or boolean {value!r} is forbidden in monetary calculations; pass str, int, or Decimal."
        )
    try:
        dec = Decimal(value) if not isinstance(value, Decimal) else value
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise InvalidMonetaryValueError(f"Cannot parse monetary Decimal from {value!r}") from exc

    if not dec.is_finite():
        raise InvalidMonetaryValueError(f"Non-finite Decimal {value!r} is forbidden.")
    return dec


@dataclass(frozen=True, slots=True)
class MoneyAmount:
    """Immutable monetary value paired with an explicit unit to prevent 10x RLS/IRT bugs."""

    amount: Decimal
    unit: CurrencyUnit
    asset_symbol: str = ""

    def __init__(
        self,
        amount: str | int | Decimal,
        unit: CurrencyUnit | str,
        *,
        asset_symbol: str = "",
    ) -> None:
        parsed_amount = parse_exact_decimal(amount)
        parsed_unit = CurrencyUnit(str(unit).upper())
        normalized_symbol = asset_symbol.strip().upper()
        if parsed_unit == CurrencyUnit.CRYPTO and not normalized_symbol:
            raise InvalidMonetaryValueError(
                "MoneyAmount with unit=CRYPTO requires an explicit asset_symbol (e.g., 'BTC')."
            )
        object.__setattr__(self, "amount", parsed_amount)
        object.__setattr__(self, "unit", parsed_unit)
        object.__setattr__(self, "asset_symbol", normalized_symbol)

    def _assert_compatible(self, other: MoneyAmount) -> None:
        if self.unit != other.unit or self.asset_symbol != other.asset_symbol:
            raise CurrencyUnitMismatchError(
                f"Cannot combine {self.unit.value}({self.asset_symbol or '-'}) "
                f"with {other.unit.value}({other.asset_symbol or '-'}). Convert explicitly first."
            )

    def __add__(self, other: MoneyAmount) -> MoneyAmount:
        self._assert_compatible(other)
        return MoneyAmount(self.amount + other.amount, self.unit, asset_symbol=self.asset_symbol)

    def __sub__(self, other: MoneyAmount) -> MoneyAmount:
        self._assert_compatible(other)
        return MoneyAmount(self.amount - other.amount, self.unit, asset_symbol=self.asset_symbol)

    def multiply_scalar(self, factor: str | int | Decimal) -> MoneyAmount:
        scalar = parse_exact_decimal(factor)
        return MoneyAmount(self.amount * scalar, self.unit, asset_symbol=self.asset_symbol)

    def quantize_down(self, step: str | Decimal) -> MoneyAmount:
        """Floor-quantize to exchange lot/tick increment (safe for order sizing)."""
        quantum = parse_exact_decimal(step)
        if quantum <= Decimal("0"):
            raise InvalidMonetaryValueError(f"Quantization step must be positive, got {step!r}.")
        steps = (self.amount / quantum).to_integral_value(rounding=ROUND_DOWN)
        return MoneyAmount(steps * quantum, self.unit, asset_symbol=self.asset_symbol)

    def quantize_nearest(self, step: str | Decimal) -> MoneyAmount:
        """Round half-up to a display or accounting precision increment."""
        quantum = parse_exact_decimal(step)
        if quantum <= Decimal("0"):
            raise InvalidMonetaryValueError(f"Quantization step must be positive, got {step!r}.")
        steps = (self.amount / quantum).to_integral_value(rounding=ROUND_HALF_UP)
        return MoneyAmount(steps * quantum, self.unit, asset_symbol=self.asset_symbol)

    def to_irt(self) -> MoneyAmount:
        """Convert RLS or IRT amount to IRT (`1 IRT = 10 RLS`)."""
        if self.unit == CurrencyUnit.IRT:
            return self
        if self.unit == CurrencyUnit.RLS:
            return MoneyAmount(self.amount / RLS_PER_IRT, CurrencyUnit.IRT)
        raise CurrencyUnitMismatchError(f"Cannot convert {self.unit.value} directly to IRT.")

    def to_rls(self) -> MoneyAmount:
        """Convert IRT or RLS amount to RLS (`1 IRT = 10 RLS`)."""
        if self.unit == CurrencyUnit.RLS:
            return self
        if self.unit == CurrencyUnit.IRT:
            return MoneyAmount(self.amount * RLS_PER_IRT, CurrencyUnit.RLS)
        raise CurrencyUnitMismatchError(f"Cannot convert {self.unit.value} directly to RLS.")


def rls_to_irt(rls_value: str | int | Decimal) -> Decimal:
    """Convert raw Nobitex Rial value to Toman (`RLS / 10`)."""
    return MoneyAmount(rls_value, CurrencyUnit.RLS).to_irt().amount


def irt_to_rls(irt_value: str | int | Decimal) -> Decimal:
    """Convert Toman value to raw Nobitex Rial (`IRT * 10`)."""
    return MoneyAmount(irt_value, CurrencyUnit.IRT).to_rls().amount
