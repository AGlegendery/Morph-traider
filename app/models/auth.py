"""Operator authentication ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from werkzeug.security import check_password_hash, generate_password_hash

from app.core.utilities.time import utc_now
from app.extensions import db


class OperatorUser(db.Model):
    """Human operator account authorized to inspect and manage Morph-Traider."""

    __tablename__ = "operator_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def set_password(self, raw_password: str) -> None:
        if len(raw_password) < 8:
            raise ValueError("Operator password must be at least 8 characters long.")
        self.password_hash = generate_password_hash(raw_password)

    def verify_password(self, candidate_password: str) -> bool:
        if not candidate_password:
            return False
        return check_password_hash(self.password_hash, candidate_password)
