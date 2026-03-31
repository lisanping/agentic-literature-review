"""Project sharing API — share/list/update/revoke — v0.4."""

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import check_project_access, get_current_user, get_current_user_optional, get_db
from app.models.project_share import ProjectShare
from app.models.user import User
from app.schemas.share import ProjectShareCreate, ProjectShareResponse, ProjectShareUpdate
from app.services.audit import log_action

logger = structlog.stdlib.get_logger()

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/shares",
    tags=["shares"],
)


@router.post("", response_model=ProjectShareResponse, status_code=201)
async def share_project(
    project_id: str,
    body: ProjectShareCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectShareResponse:
    """Share a project with another user (owner or admin only)."""
    project = await check_project_access(project_id, db, user, min_permission="owner")

    # Find target user by email
    result = await db.execute(
        select(User).where(User.email == body.email, User.is_active.is_(True))
    )
    target_user = result.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if target_user.id == user.id:
        raise HTTPException(status_code=400, detail="Cannot share with yourself")

    # Check if already shared (active)
    existing = await db.execute(
        select(ProjectShare).where(
            ProjectShare.project_id == project_id,
            ProjectShare.user_id == target_user.id,
            ProjectShare.revoked_at.is_(None),
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Project already shared with this user")

    share = ProjectShare(
        project_id=project_id,
        user_id=target_user.id,
        permission=body.permission,
        shared_by=user.id,
    )
    db.add(share)

    await log_action(
        db,
        action="share_project",
        user_id=user.id,
        resource_type="project",
        resource_id=project_id,
        details={"shared_with": target_user.id, "permission": body.permission},
    )

    await db.commit()
    await db.refresh(share)

    logger.info("project.shared", project_id=project_id, shared_with=target_user.id)

    return ProjectShareResponse(
        id=share.id,
        project_id=share.project_id,
        user_id=share.user_id,
        username=target_user.username,
        email=target_user.email,
        permission=share.permission,
        created_at=share.created_at,
    )


@router.get("", response_model=list[ProjectShareResponse])
async def list_shares(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectShareResponse]:
    """List all active shares for a project (owner or admin)."""
    await check_project_access(project_id, db, user, min_permission="owner")

    result = await db.execute(
        select(ProjectShare, User)
        .join(User, ProjectShare.user_id == User.id)
        .where(
            ProjectShare.project_id == project_id,
            ProjectShare.revoked_at.is_(None),
        )
    )
    rows = result.all()

    return [
        ProjectShareResponse(
            id=share.id,
            project_id=share.project_id,
            user_id=share.user_id,
            username=u.username,
            email=u.email,
            permission=share.permission,
            created_at=share.created_at,
        )
        for share, u in rows
    ]


@router.patch("/{share_id}", response_model=ProjectShareResponse)
async def update_share(
    project_id: str,
    share_id: str,
    body: ProjectShareUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectShareResponse:
    """Update share permission (owner or admin only)."""
    await check_project_access(project_id, db, user, min_permission="owner")

    result = await db.execute(
        select(ProjectShare).where(
            ProjectShare.id == share_id,
            ProjectShare.project_id == project_id,
            ProjectShare.revoked_at.is_(None),
        )
    )
    share = result.scalar_one_or_none()
    if share is None:
        raise HTTPException(status_code=404, detail="Share not found")

    share.permission = body.permission
    await db.commit()
    await db.refresh(share)

    # Fetch user info for response
    u_result = await db.execute(select(User).where(User.id == share.user_id))
    target_user = u_result.scalar_one()

    return ProjectShareResponse(
        id=share.id,
        project_id=share.project_id,
        user_id=share.user_id,
        username=target_user.username,
        email=target_user.email,
        permission=share.permission,
        created_at=share.created_at,
    )


@router.delete("/{share_id}", status_code=204)
async def revoke_share(
    project_id: str,
    share_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke a share (owner or admin only)."""
    await check_project_access(project_id, db, user, min_permission="owner")

    result = await db.execute(
        select(ProjectShare).where(
            ProjectShare.id == share_id,
            ProjectShare.project_id == project_id,
            ProjectShare.revoked_at.is_(None),
        )
    )
    share = result.scalar_one_or_none()
    if share is None:
        raise HTTPException(status_code=404, detail="Share not found")

    share.revoked_at = datetime.now(timezone.utc)

    await log_action(
        db,
        action="revoke_share",
        user_id=user.id,
        resource_type="project",
        resource_id=project_id,
        details={"revoked_user": share.user_id},
    )

    await db.commit()
    logger.info("project.share_revoked", project_id=project_id, share_id=share_id)
