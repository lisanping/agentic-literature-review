"""User ORM model — v0.4 authentication."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    username: Mapped[str] = mapped_column(String, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    preferences: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_users_email", "email", unique=True),
        Index(
            "idx_users_role",
            "role",
            sqlite_where=is_active.is_(True),
        ),
    )
