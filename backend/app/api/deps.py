"""Dependency injection for API routes."""

from collections.abc import AsyncGenerator

import jwt
import redis.asyncio as aioredis
import structlog
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import async_session_factory
from app.models.project import Project
from app.models.project_share import ProjectShare
from app.models.user import User
from app.services.auth import decode_access_token

logger = structlog.stdlib.get_logger()

# ── Redis client ──
_redis_client: aioredis.Redis | None = None


def _get_redis_client() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
    return _redis_client


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_redis() -> aioredis.Redis:
    """Return the shared Redis client."""
    return _get_redis_client()


# ── Authentication dependencies ──


async def get_current_user(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate current user from Bearer token. Raises 401 on failure."""
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization[7:]  # strip "Bearer "
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user


async def get_current_user_optional(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Optional authentication — returns None when AUTH_REQUIRED=false and no token."""
    if authorization is None or not authorization.startswith("Bearer "):
        if not settings.AUTH_REQUIRED:
            return None
        raise HTTPException(status_code=401, detail="Authentication required")

    return await get_current_user(authorization=authorization, db=db)


def require_role(role: str):
    """Dependency factory: require current user to have a specific role (or admin)."""

    async def check(user: User = Depends(get_current_user)) -> User:
        if user.role != role and user.role != "admin":
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return check


# Permission levels for comparison
_PERMISSION_LEVELS = {"viewer": 0, "collaborator": 1, "owner": 2}


async def check_project_access(
    project_id: str,
    db: AsyncSession,
    user: User | None,
    min_permission: str = "viewer",
) -> Project:
    """Check if user has at least `min_permission` on a project.

    Access is granted if:
    - user is the project owner (user_id matches)
    - user has a share with permission >= min_permission
    - user is admin
    - AUTH_REQUIRED=false and user is None (backward compat)

    Returns the Project or raises 403/404.
    """
    from app.api.exceptions import NotFoundError

    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.deleted_at.is_(None),
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise NotFoundError("project", project_id)

    # No auth mode — allow all
    if user is None:
        return project

    # Admin bypasses all checks
    if user.role == "admin":
        return project

    # Owner has full access
    if project.user_id == user.id:
        return project

    # Check shares
    min_level = _PERMISSION_LEVELS.get(min_permission, 0)
    share_result = await db.execute(
        select(ProjectShare).where(
            ProjectShare.project_id == project_id,
            ProjectShare.user_id == user.id,
            ProjectShare.revoked_at.is_(None),
        )
    )
    share = share_result.scalar_one_or_none()
    if share is not None:
        share_level = _PERMISSION_LEVELS.get(share.permission, 0)
        if share_level >= min_level:
            return project

    raise HTTPException(status_code=403, detail="Insufficient project permissions")
