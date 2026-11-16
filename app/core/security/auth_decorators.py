"""Route decorator enforcing authenticated, active operator sessions."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import session

from app.core.exceptions import AuthenticationRequiredError
from app.models.auth import OperatorUser
from app.repositories.operator_repository import OperatorRepository

SESSION_OPERATOR_ID_KEY = "operator_user_id"


def get_authenticated_operator() -> OperatorUser | None:
    """Resolve the active OperatorUser from the signed request session cookie."""
    raw_id = session.get(SESSION_OPERATOR_ID_KEY)
    if raw_id is None:
        return None

    try:
        operator_id = int(raw_id)
    except (TypeError, ValueError):
        session.clear()
        return None

    operator = OperatorRepository().get_by_id(operator_id)
    if operator is None or not operator.is_active:
        session.clear()
        return None

    return operator


def require_operator_auth(view_func: Callable[..., Any]) -> Callable[..., Any]:
    """Require an active authenticated operator session; raise 401 JSON error otherwise."""

    @wraps(view_func)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        operator = get_authenticated_operator()
        if operator is None:
            raise AuthenticationRequiredError("Operator authentication required.")
        return view_func(*args, **kwargs)

    return wrapped
