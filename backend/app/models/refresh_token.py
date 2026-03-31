"""RefreshToken ORM model — v0.4 JWT token rotation."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_refresh_tokens_user", "user_id"),
        Index("idx_refresh_tokens_expires", "expires_at"),
    )
