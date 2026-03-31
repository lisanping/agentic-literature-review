"""User management API — profile + admin operations — v0.4."""

import math

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.models.user import User
from app.schemas.user import (
    AdminUserUpdate,
    PasswordChange,
    UserResponse,
    UserUpdate,
)
from app.services.auth import hash_password, verify_password

logger = structlog.stdlib.get_logger()

router = APIRouter(prefix="/api/v1/users", tags=["users"])


# ── Current user endpoints ──


@router.get("/me", response_model=UserResponse)
async def get_me(
    user: User = Depends(get_current_user),
) -> UserResponse:
    """Get current authenticated user profile."""
    return UserResponse.model_validate(user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    body: UserUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update current user profile."""
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.put("/me/password", status_code=204)
async def change_password(
    body: PasswordChange,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Change current user's password."""
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    user.hashed_password = hash_password(body.new_password)
    await db.commit()
    logger.info("user.password_changed", user_id=user.id)


# ── Admin endpoints ──


@router.get("", response_model=dict)
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List all users (admin only)."""
    count_q = select(func.count(User.id))
    total = (await db.execute(count_q)).scalar() or 0
    pages = max(1, math.ceil(total / size))

    q = (
        select(User)
        .order_by(User.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    result = await db.execute(q)
    items = [UserResponse.model_validate(u) for u in result.scalars().all()]

    return {"items": items, "total": total, "page": page, "size": size, "pages": pages}


@router.patch("/{user_id}", response_model=UserResponse)
async def admin_update_user(
    user_id: str,
    body: AdminUserUpdate,
    admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update a user's role or active status (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(target, key, value)
    await db.commit()
    await db.refresh(target)
    return UserResponse.model_validate(target)


@router.delete("/{user_id}", status_code=204)
async def deactivate_user(
    user_id: str,
    admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Deactivate a user account (admin only). Soft-disable, not delete."""
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    target.is_active = False
    await db.commit()
    logger.info("user.deactivated", user_id=user_id, by=admin.id)
