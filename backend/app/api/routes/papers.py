"""Paper management API — list/status/detail/upload — §8.3.3."""

import math

from fastapi import APIRouter, Depends, Query, UploadFile, File
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.api.exceptions import NotFoundError
from app.models.paper import Paper
from app.models.project import Project
from app.models.project_paper import ProjectPaper
from app.schemas.output import PaginatedResponse
from app.schemas.paper import PaperResponse, ProjectPaperResponse

router = APIRouter(tags=["papers"])


@router.get(
    "/api/v1/projects/{project_id}/papers",
    response_model=PaginatedResponse,
)
async def list_project_papers(
    project_id: str,
    status: str | None = Query(None, pattern=r"^(candidate|selected|excluded)$"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse:
    """List papers in a project with optional status filter."""
    await _ensure_project_exists(project_id, db)

    q = (
        select(ProjectPaper)
        .options(selectinload(ProjectPaper.paper))
        .where(
            ProjectPaper.project_id == project_id,
            ProjectPaper.deleted_at.is_(None),
        )
    )
    count_q = select(func.count(ProjectPaper.id)).where(
        ProjectPaper.project_id == project_id,
        ProjectPaper.deleted_at.is_(None),
    )

    if status:
        q = q.where(ProjectPaper.status == status)
        count_q = count_q.where(ProjectPaper.status == status)

    total = (await db.execute(count_q)).scalar() or 0
    pages = max(1, math.ceil(total / size))

    q = q.order_by(ProjectPaper.relevance_rank.asc().nullslast()).offset(
        (page - 1) * size
    ).limit(size)
    result = await db.execute(q)
    rows = result.scalars().all()

    items = [_to_project_paper_response(pp) for pp in rows]
    return PaginatedResponse(items=items, total=total, page=page, size=size, pages=pages)


@router.patch(
    "/api/v1/projects/{project_id}/papers/{paper_id}",
    response_model=ProjectPaperResponse,
)
async def update_paper_status(
    project_id: str,
    paper_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
) -> ProjectPaperResponse:
    """Update a paper's status within a project (candidate → selected / excluded)."""
    result = await db.execute(
        select(ProjectPaper)
        .options(selectinload(ProjectPaper.paper))
        .where(
            ProjectPaper.project_id == project_id,
            ProjectPaper.paper_id == paper_id,
            ProjectPaper.deleted_at.is_(None),
        )
    )
    pp = result.scalar_one_or_none()
    if pp is None:
        raise NotFoundError("paper", paper_id)

    new_status = body.get("status")
    if new_status in ("selected", "excluded", "candidate"):
        pp.status = new_status

    await db.commit()
    await db.refresh(pp)
    return _to_project_paper_response(pp)


@router.get("/api/v1/papers/{paper_id}", response_model=PaperResponse)
async def get_paper_detail(
    paper_id: str,
    db: AsyncSession = Depends(get_db),
) -> PaperResponse:
    """Get paper detail with analysis."""
    result = await db.execute(select(Paper).where(Paper.id == paper_id))
    paper = result.scalar_one_or_none()
    if paper is None:
        raise NotFoundError("paper", paper_id)
    return PaperResponse.model_validate(paper)


@router.post(
    "/api/v1/projects/{project_id}/papers/upload",
    response_model=list[PaperResponse],
)
async def upload_papers(
    project_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> list[PaperResponse]:
    """Upload a PDF or BibTeX/RIS file to add papers to a project.

    For MVP, this stores the file and creates a placeholder paper entry.
    Full parsing (BibTeX import, PDF metadata extraction) will be enhanced later.
    """
    await _ensure_project_exists(project_id, db)

    content = await file.read()
    filename = file.filename or "uploaded"

    # Create a placeholder paper from the uploaded file
    paper = Paper(
        title=filename,
        authors=[],
        source="upload",
        pdf_path=None,  # would save to disk in full implementation
    )
    db.add(paper)
    await db.flush()

    pp = ProjectPaper(
        project_id=project_id,
        paper_id=paper.id,
        status="candidate",
        found_by="upload",
    )
    db.add(pp)
    await db.commit()
    await db.refresh(paper)

    return [PaperResponse.model_validate(paper)]


def _to_project_paper_response(pp: ProjectPaper) -> ProjectPaperResponse:
    return ProjectPaperResponse(
        paper=PaperResponse.model_validate(pp.paper),
        status=pp.status,
        found_by=pp.found_by,
        relevance_rank=pp.relevance_rank,
        added_at=pp.added_at,
    )


async def _ensure_project_exists(project_id: str, db: AsyncSession) -> None:
    result = await db.execute(
        select(Project.id).where(
            Project.id == project_id,
            Project.deleted_at.is_(None),
        )
    )
    if result.scalar_one_or_none() is None:
        raise NotFoundError("project", project_id)
