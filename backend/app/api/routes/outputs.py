"""Output & export API — list/detail/export — §8.3.4."""

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.exceptions import NotFoundError
from app.models.project import Project
from app.models.review_output import ReviewOutput
from app.schemas.output import ReviewOutputResponse
from app.schemas.workflow import ExportRequest
from app.services.export import export_bibtex, export_markdown, export_ris, export_word

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/outputs",
    tags=["outputs"],
)


@router.get("", response_model=list[ReviewOutputResponse])
async def list_outputs(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[ReviewOutputResponse]:
    """List all outputs for a project."""
    await _ensure_project_exists(project_id, db)

    result = await db.execute(
        select(ReviewOutput)
        .where(
            ReviewOutput.project_id == project_id,
            ReviewOutput.deleted_at.is_(None),
        )
        .order_by(ReviewOutput.created_at.desc())
    )
    outputs = result.scalars().all()
    return [ReviewOutputResponse.model_validate(o) for o in outputs]


@router.get("/{output_id}", response_model=ReviewOutputResponse)
async def get_output(
    project_id: str,
    output_id: str,
    db: AsyncSession = Depends(get_db),
) -> ReviewOutputResponse:
    """Get a single output detail."""
    output = await _get_output_or_404(project_id, output_id, db)
    return ReviewOutputResponse.model_validate(output)


@router.post("/{output_id}/export")
async def export_output(
    project_id: str,
    output_id: str,
    body: ExportRequest,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Export an output to a specific format (markdown/word/bibtex/ris).

    Returns the file as a download.
    """
    output = await _get_output_or_404(project_id, output_id, db)

    content_text = output.content or ""
    references = output.references or []
    title = output.title

    fmt = body.format
    if fmt == "markdown":
        data = export_markdown(content_text, references, title).encode("utf-8")
        media_type = "text/markdown; charset=utf-8"
        filename = f"{title or 'review'}.md"
    elif fmt == "word":
        data = export_word(content_text, references, title)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"{title or 'review'}.docx"
    elif fmt == "bibtex":
        data = export_bibtex(references).encode("utf-8")
        media_type = "application/x-bibtex; charset=utf-8"
        filename = f"{title or 'references'}.bib"
    elif fmt == "ris":
        data = export_ris(references).encode("utf-8")
        media_type = "application/x-research-info-systems; charset=utf-8"
        filename = f"{title or 'references'}.ris"
    else:
        data = content_text.encode("utf-8")
        media_type = "text/plain; charset=utf-8"
        filename = f"{title or 'review'}.txt"

    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _get_output_or_404(
    project_id: str, output_id: str, db: AsyncSession
) -> ReviewOutput:
    result = await db.execute(
        select(ReviewOutput).where(
            ReviewOutput.id == output_id,
            ReviewOutput.project_id == project_id,
            ReviewOutput.deleted_at.is_(None),
        )
    )
    output = result.scalar_one_or_none()
    if output is None:
        raise NotFoundError("output", output_id)
    return output


async def _ensure_project_exists(project_id: str, db: AsyncSession) -> None:
    result = await db.execute(
        select(Project.id).where(
            Project.id == project_id,
            Project.deleted_at.is_(None),
        )
    )
    if result.scalar_one_or_none() is None:
        raise NotFoundError("project", project_id)
