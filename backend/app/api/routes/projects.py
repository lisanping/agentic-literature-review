"""Project management API — CRUD + pagination — §8.3.1."""

import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.exceptions import NotFoundError
from app.models.project import Project
from app.schemas.output import PaginatedResponse
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Create a new literature review project."""
    project = Project(
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
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse:
    """List projects with optional status filter and pagination."""
    q = select(Project).where(Project.deleted_at.is_(None))
    count_q = select(func.count(Project.id)).where(Project.deleted_at.is_(None))

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
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Get project details."""
    project = await _get_project_or_404(project_id, db)
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Partially update project configuration."""
    project = await _get_project_or_404(project_id, db)
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
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete a project."""
    project = await _get_project_or_404(project_id, db)
    from datetime import datetime, timezone

    project.deleted_at = datetime.now(timezone.utc)
    await db.commit()


async def _get_project_or_404(
    project_id: str, db: AsyncSession
) -> Project:
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.deleted_at.is_(None),
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise NotFoundError("project", project_id)
    return project
