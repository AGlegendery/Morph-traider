"""Repository for OperatorUser lookup and idempotent initial account bootstrap."""

from __future__ import annotations

from app.core.utilities.time import utc_now
from app.extensions import db
from app.models.auth import OperatorUser


class OperatorRepository:
    """Data-access methods for operator authentication."""

    def get_by_id(self, operator_id: int) -> OperatorUser | None:
        return db.session.get(OperatorUser, operator_id)

    def get_by_username(self, username: str) -> OperatorUser | None:
        normalized = username.strip()
        if not normalized:
            return None
        return db.session.query(OperatorUser).filter_by(username=normalized).one_or_none()

    def create_operator(
        self,
        *,
        username: str,
        raw_password: str | None = None,
        prehashed_password: str | None = None,
    ) -> OperatorUser:
        clean_username = username.strip()
        if not clean_username:
            raise ValueError("Operator username must be non-empty.")

        user = OperatorUser(username=clean_username, password_hash="", is_active=True)
        if prehashed_password:
            user.password_hash = prehashed_password.strip()
        elif raw_password:
            user.set_password(raw_password)
        else:
            raise ValueError("Either raw_password or prehashed_password must be supplied.")

        db.session.add(user)
        db.session.commit()
        return user

    def ensure_bootstrap_operator(
        self,
        *,
        username: str,
        password_hash: str,
    ) -> OperatorUser | None:
        """Create configured initial operator once if username & precomputed hash are set."""
        clean_user = username.strip()
        clean_hash = password_hash.strip()
        if not clean_user or not clean_hash:
            return None
        existing = self.get_by_username(clean_user)
        if existing is not None:
            return existing
        return self.create_operator(username=clean_user, prehashed_password=clean_hash)

    def mark_logged_in(self, operator: OperatorUser) -> None:
        operator.last_login_at = utc_now()
        db.session.commit()
