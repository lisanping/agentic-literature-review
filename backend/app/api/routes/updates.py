"""Update API — trigger update checks and view update history — v0.5."""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import check_project_access, get_current_user_optional, get_db
from app.models.review_output import ReviewOutput
from app.models.user import User

logger = structlog.stdlib.get_logger()

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/updates",
    tags=["updates"],
)


@router.post("")
async def trigger_update(
    project_id: str,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger an asynchronous update check for new literature.

    Dispatches a Celery task that runs the Update Agent.
    Requires collaborator permission.
    """
    from app.models.project import Project

    project = await check_project_access(
        project_id, db, user, min_permission="collaborator"
    )

    # Verify project has completed at least one review
    if project.status not in ("completed", "updating"):
        raise HTTPException(
            status_code=400,
            detail="Project must have a completed review before checking for updates.",
        )

    # Dispatch Celery task
    from app.tasks import run_update

    task = run_update.delay(project_id)
    logger.info("update.triggered", project_id=project_id, task_id=task.id)

    return {"task_id": task.id, "status": "queued"}


@router.get("")
async def list_updates(
    project_id: str,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List update history for a project.

    Returns update reports in reverse chronological order.
    """
    await check_project_access(project_id, db, user, min_permission="viewer")

    result = await db.execute(
        select(ReviewOutput)
        .where(
            ReviewOutput.project_id == project_id,
            ReviewOutput.output_type == "update_report",
            ReviewOutput.deleted_at.is_(None),
        )
        .order_by(ReviewOutput.created_at.desc())
    )
    outputs = result.scalars().all()

    return [
        {
            "id": o.id,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "new_papers_count": (o.structured_data or {}).get("new_papers_count", 0),
            "checked_at": (o.structured_data or {}).get("checked_at"),
        }
        for o in outputs
    ]


@router.get("/{update_id}")
async def get_update_detail(
    project_id: str,
    update_id: str,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get detailed update report including new papers and report text."""
    await check_project_access(project_id, db, user, min_permission="viewer")

    result = await db.execute(
        select(ReviewOutput).where(
            ReviewOutput.id == update_id,
            ReviewOutput.project_id == project_id,
            ReviewOutput.output_type == "update_report",
            ReviewOutput.deleted_at.is_(None),
        )
    )
    output = result.scalar_one_or_none()
    if not output:
        raise HTTPException(status_code=404, detail="Update report not found.")

    structured = output.structured_data or {}
    return {
        "id": output.id,
        "project_id": project_id,
        "created_at": output.created_at.isoformat() if output.created_at else None,
        "report": output.content,
        "new_papers": structured.get("new_papers", []),
        "new_papers_count": structured.get("new_papers_count", 0),
        "checked_at": structured.get("checked_at"),
    }
