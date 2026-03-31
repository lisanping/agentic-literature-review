"""Project management API — CRUD + pagination — §8.3.1."""

import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import check_project_access, get_current_user_optional, get_db
from app.api.exceptions import NotFoundError
from app.models.project import Project
from app.models.project_share import ProjectShare
from app.models.user import User
from app.schemas.output import PaginatedResponse
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: ProjectCreate,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Create a new literature review project."""
    project = Project(
        user_id=user.id if user else None,
        user_query=body.user_query,
        title=body.user_query[:120],
        output_types=[t.value for t in body.output_types],
        output_language=body.output_language,
        citation_style=body.citation_style.value,
        search_config=body.search_config,
        token_budget=body.token_budget,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get("", response_model=PaginatedResponse)
async def list_projects(
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse:
    """List projects with optional status filter and pagination."""
    q = select(Project).where(Project.deleted_at.is_(None))
    count_q = select(func.count(Project.id)).where(Project.deleted_at.is_(None))

    # Filter by user ownership or shared access
    if user is not None:
        shared_ids = (
            select(ProjectShare.project_id)
            .where(ProjectShare.user_id == user.id, ProjectShare.revoked_at.is_(None))
        )
        if user.role != "admin":
            user_filter = or_(Project.user_id == user.id, Project.id.in_(shared_ids))
            q = q.where(user_filter)
            count_q = count_q.where(user_filter)

    if status:
        q = q.where(Project.status == status)
        count_q = count_q.where(Project.status == status)

    total = (await db.execute(count_q)).scalar() or 0
    pages = max(1, math.ceil(total / size))

    q = q.order_by(Project.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(q)
    items = [ProjectResponse.model_validate(p) for p in result.scalars().all()]

    return PaginatedResponse(items=items, total=total, page=page, size=size, pages=pages)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Get project details."""
    project = await check_project_access(project_id, db, user, min_permission="viewer")
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Partially update project configuration."""
    project = await check_project_access(project_id, db, user, min_permission="owner")
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "output_types" and value is not None:
            value = [t.value if hasattr(t, "value") else t for t in value]
        if key == "citation_style" and value is not None:
            value = value.value if hasattr(value, "value") else value
        setattr(project, key, value)
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete a project."""
    project = await check_project_access(project_id, db, user, min_permission="owner")
    from datetime import datetime, timezone

    project.deleted_at = datetime.now(timezone.utc)
    await db.commit()
