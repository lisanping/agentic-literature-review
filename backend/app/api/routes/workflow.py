"""Workflow control API — start/resume/status/cancel — §8.3.2."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.exceptions import ConflictError, NotFoundError
from app.models.project import Project
from app.schemas.workflow import HitlFeedback, WorkflowStartResponse, WorkflowStatusResponse

router = APIRouter(prefix="/api/v1/projects/{project_id}/workflow", tags=["workflow"])


@router.post("/start", response_model=WorkflowStartResponse)
async def start_workflow(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> WorkflowStartResponse:
    """Start the literature review workflow for a project.

    Dispatches a Celery task to execute the workflow asynchronously.
    """
    project = await _get_project_or_404(project_id, db)

    if project.status in ("searching", "reading", "writing", "analyzing"):
        raise ConflictError(
            message=f"Workflow already running (status={project.status})",
            code="WORKFLOW_ALREADY_RUNNING",
        )

    project.status = "searching"
    project.thread_id = project.id  # use project id as LangGraph thread
    await db.commit()

    # Dispatch Celery task
    from app.tasks import run_review_segment

    task = run_review_segment.delay(
        project_id=project.id,
        config={
            "user_query": project.user_query,
            "output_types": project.output_types,
            "output_language": project.output_language,
            "citation_style": project.citation_style,
            "token_budget": project.token_budget,
            "search_config": project.search_config,
        },
        resume=False,
    )

    return WorkflowStartResponse(task_id=task.id, status="started")


@router.post("/resume", response_model=WorkflowStartResponse)
async def resume_workflow(
    project_id: str,
    body: HitlFeedback,
    db: AsyncSession = Depends(get_db),
) -> WorkflowStartResponse:
    """Resume workflow after HITL feedback submission."""
    project = await _get_project_or_404(project_id, db)

    # Build state update from HITL feedback
    state_update = _build_state_update(body)

    from app.tasks import run_review_segment

    task = run_review_segment.delay(
        project_id=project.id,
        config=state_update,
        resume=True,
    )

    return WorkflowStartResponse(task_id=task.id, status="resumed")


@router.get("/status", response_model=WorkflowStatusResponse)
async def get_workflow_status(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> WorkflowStatusResponse:
    """Get current workflow status and progress."""
    project = await _get_project_or_404(project_id, db)
    return WorkflowStatusResponse(
        project_id=project.id,
        phase=project.status,
        status=project.status,
        token_usage=project.token_usage,
    )


@router.post("/cancel", status_code=204)
async def cancel_workflow(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Cancel a running workflow."""
    project = await _get_project_or_404(project_id, db)
    project.status = "cancelled"
    await db.commit()


def _build_state_update(feedback: HitlFeedback) -> dict:
    """Convert HitlFeedback to ReviewState partial update."""
    update: dict = {}

    if feedback.hitl_type == "search_review":
        if feedback.selected_paper_ids is not None:
            update["selected_paper_ids"] = feedback.selected_paper_ids
        if feedback.additional_query:
            update["needs_more_search"] = True
            update["feedback_search_queries"] = [feedback.additional_query]
        else:
            update["needs_more_search"] = False
        update["hitl_type"] = "search_review"

    elif feedback.hitl_type == "outline_review":
        if feedback.approved_outline:
            update["outline"] = feedback.approved_outline
        update["hitl_type"] = "outline_review"

    elif feedback.hitl_type == "draft_review":
        if not feedback.approved and feedback.revision_instructions:
            update["revision_instructions"] = feedback.revision_instructions
        else:
            update["revision_instructions"] = ""
        update["hitl_type"] = "draft_review"

    return update


async def _get_project_or_404(project_id: str, db: AsyncSession) -> Project:
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
