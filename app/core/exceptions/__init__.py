"""Domain, configuration, security, and financial safety exceptions."""

from __future__ import annotations


class MorphTraiderError(Exception):
    """Base exception for all Morph-Traider application errors."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, message: str, *, error_code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if error_code is not None:
            self.error_code = error_code


class FinancialSafetyLockError(MorphTraiderError):
    """Raised immediately if any configuration or call attempts to bypass Paper-Trading locks."""

    status_code = 403
    error_code = "financial_safety_lock_violation"


class ConfigurationError(MorphTraiderError):
    """Raised when required application configuration is invalid or missing."""

    status_code = 500
    error_code = "configuration_error"


class SecurityAuthorizationError(MorphTraiderError):
    """Raised when operator authentication or webhook/cron signature verification fails."""

    status_code = 403
    error_code = "authorization_failed"


class AuthenticationRequiredError(MorphTraiderError):
    """Raised when an unauthenticated request targets an operator-protected endpoint."""

    status_code = 401
    error_code = "authentication_required"


class CurrencyUnitMismatchError(MorphTraiderError):
    """Raised when arithmetic or comparison mixes incompatible currency units (e.g., RLS vs IRT)."""

    status_code = 400
    error_code = "currency_unit_mismatch"


class InvalidMonetaryValueError(MorphTraiderError):
    """Raised when binary floats, NaNs, or invalid decimals are passed into monetary math."""

    status_code = 400
    error_code = "invalid_monetary_value"


class TaskLockConflictError(MorphTraiderError):
    """Raised when a scheduled task lease is currently held by another active WSGI worker."""

    status_code = 409
    error_code = "task_lock_conflict"
