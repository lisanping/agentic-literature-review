"""Authentication API routes — register / login / refresh / logout — v0.4."""

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.user import (
    TokenRefresh,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.services.auth import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    refresh_token_expires_at,
    verify_password,
)
from app.config import settings

logger = structlog.stdlib.get_logger()

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    body: UserRegister,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Register a new user and return JWT tokens."""
    # Check email uniqueness
    existing = await db.execute(
        select(User).where(User.email == body.email)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=body.email,
        username=body.username,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    await db.flush()

    # Issue tokens
    tokens = await _issue_tokens(user, db)
    await db.commit()

    logger.info("user.registered", user_id=user.id, email=user.email)
    return tokens


@router.post("/login", response_model=TokenResponse)
async def login(
    body: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate user and return JWT tokens."""
    result = await db.execute(
        select(User).where(User.email == body.email, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Update last login
    user.last_login_at = datetime.now(timezone.utc)

    tokens = await _issue_tokens(user, db)
    await db.commit()

    logger.info("user.login", user_id=user.id)
    return tokens


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: TokenRefresh,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Refresh access token using a valid refresh token (rotation)."""
    token_hash = hash_refresh_token(body.refresh_token)

    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
        )
    )
    stored_token = result.scalar_one_or_none()

    if stored_token is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if stored_token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token expired")

    # Revoke the used token (one-time use / rotation)
    stored_token.revoked_at = datetime.now(timezone.utc)

    # Load user
    user_result = await db.execute(
        select(User).where(User.id == stored_token.user_id, User.is_active.is_(True))
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    tokens = await _issue_tokens(user, db)
    await db.commit()

    logger.info("token.refreshed", user_id=user.id)
    return tokens


@router.post("/logout", status_code=204)
async def logout(
    body: TokenRefresh,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke the provided refresh token."""
    token_hash = hash_refresh_token(body.refresh_token)

    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    stored_token = result.scalar_one_or_none()

    if stored_token is not None:
        stored_token.revoked_at = datetime.now(timezone.utc)
        await db.commit()

    logger.info("user.logout", user_id=user.id)


# ── Helpers ──


async def _issue_tokens(user: User, db: AsyncSession) -> TokenResponse:
    """Create an access + refresh token pair and persist the refresh token."""
    access_token = create_access_token(user.id, user.email, user.role)
    raw_refresh = generate_refresh_token()

    refresh_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_refresh),
        expires_at=refresh_token_expires_at(),
    )
    db.add(refresh_record)

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
