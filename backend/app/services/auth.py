"""Authentication service — password hashing, JWT encode/decode, token management."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import structlog

from app.config import settings

logger = structlog.stdlib.get_logger()


# ── Password hashing ──


def hash_password(password: str) -> str:
    """Hash a password using bcrypt with configured cost factor."""
    salt = bcrypt.gensalt(rounds=settings.BCRYPT_COST_FACTOR)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


# ── JWT ──


def create_access_token(
    user_id: str,
    email: str,
    role: str,
) -> str:
    """Create a JWT access token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token. Raises jwt.PyJWTError on failure."""
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )


# ── Refresh token ──


def generate_refresh_token() -> str:
    """Generate a cryptographically secure refresh token (random UUID-like string)."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """Hash a refresh token with SHA-256 for safe storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_token_expires_at() -> datetime:
    """Calculate expiry datetime for a new refresh token."""
    return datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
