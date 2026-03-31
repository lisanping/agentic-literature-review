"""Celery tasks — checkpoint-segmented workflow execution — §10.2."""

import asyncio
import threading

import structlog
from celery.signals import worker_shutting_down

from app.celery_app import celery_app
from app.config import settings

logger = structlog.stdlib.get_logger()

# ── Graceful shutdown flag ──
_shutting_down = threading.Event()


@worker_shutting_down.connect
def _on_worker_shutting_down(sig, how, exitcode, **kwargs):
    """Set the shutdown flag so in-flight tasks can checkpoint and exit."""
    logger.info("worker.shutting_down", signal=sig)
    _shutting_down.set()


def is_shutting_down() -> bool:
    """Check whether the Celery worker is shutting down."""
    return _shutting_down.is_set()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_review_segment(
    self,
    project_id: str,
    config: dict,
    resume: bool = False,
) -> dict:
    """Execute a workflow segment between two HITL interrupt points.

    This is a synchronous Celery task that bridges to async via
    ``asyncio.run()``. The workflow auto-checkpoints at each HITL
    ``interrupt`` node and the task ends, freeing the Celery worker.

    When the user submits HITL feedback via API, a new task is dispatched
    with ``resume=True`` to continue from the checkpoint.

    Args:
        project_id: Project ID (also used as LangGraph thread_id).
        config: Initial state config (for new) or state update (for resume).
        resume: Whether to resume from an existing checkpoint.

    Returns:
        Dict with final phase and summary info.
    """
    try:
        return asyncio.run(_run_async(project_id, config, resume))
    except Exception as exc:
        logger.error(
            "task.run_review_segment.failed",
            project_id=project_id,
            error=str(exc),
        )
        raise self.retry(exc=exc)


async def _run_async(
    project_id: str,
    config: dict,
    resume: bool,
) -> dict:
    """Async workflow execution logic."""
    from app.agents.orchestrator import compile_review_graph
    from app.services.event_publisher import EventPublisher

    graph = compile_review_graph()
    publisher = EventPublisher(settings.REDIS_URL)
    thread_config = {"configurable": {"thread_id": project_id}}

    try:
        if resume:
            # Resume from checkpoint: update state with HITL feedback, then continue
            hitl_type = config.pop("hitl_type", None)
            if hitl_type and config:
                as_node = _hitl_type_to_node(hitl_type)
                await graph.aupdate_state(thread_config, config, as_node=as_node)

            async for event in graph.astream(None, config=thread_config):
                await _publish_event(publisher, project_id, event)
        else:
            # Fresh start
            initial_state = _build_initial_state(config)
            async for event in graph.astream(initial_state, config=thread_config):
                await _publish_event(publisher, project_id, event)

        # Workflow reached an interrupt or completed
        await publisher.publish(project_id, "complete", "system", {"phase": "segment_done"})
        return {"project_id": project_id, "status": "segment_complete"}

    except Exception as exc:
        await publisher.publish(
            project_id, "error", "system", {"message": str(exc)}
        )
        raise
    finally:
        await publisher.close()


def _build_initial_state(config: dict) -> dict:
    """Build the initial ReviewState from project config."""
    return {
        "user_query": config.get("user_query", ""),
        "output_types": config.get("output_types", ["full_review"]),
        "output_language": config.get("output_language", "zh"),
        "citation_style": config.get("citation_style", "apa"),
        "token_budget": config.get("token_budget"),
        "uploaded_papers": [],
        "feedback_iteration_count": 0,
        "feedback_search_queries": [],
        "error_log": [],
    }


def _hitl_type_to_node(hitl_type: str) -> str:
    """Map HITL type to the corresponding graph node name."""
    mapping = {
        "search_review": "human_review_search",
        "outline_review": "human_review_outline",
        "draft_review": "human_review_draft",
    }
    return mapping.get(hitl_type, hitl_type)


async def _publish_event(
    publisher,
    project_id: str,
    event: dict,
) -> None:
    """Publish a workflow graph event via EventPublisher."""
    if isinstance(event, dict):
        # LangGraph stream events are node → output dicts
        for node_name, output in event.items():
            await publisher.publish(
                project_id,
                "progress",
                node_name,
                {"phase": output.get("current_phase", node_name)} if isinstance(output, dict) else {},
            )


# ── Update Agent Task (v0.5) ──


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def run_update(self, project_id: str) -> dict:
    """Execute the Update Agent for a project.

    Loads existing project data, runs incremental search + relevance
    assessment + report generation, and persists results.
    """
    try:
        return asyncio.run(_run_update_async(project_id))
    except Exception as exc:
        logger.error(
            "task.run_update.failed",
            project_id=project_id,
            error=str(exc),
        )
        raise self.retry(exc=exc)


async def _run_update_async(project_id: str) -> dict:
    """Async update execution logic."""
    from datetime import datetime, timezone

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.agents.update_agent import update_node
    from app.models.database import async_session_factory
    from app.models.project import Project
    from app.models.project_paper import ProjectPaper
    from app.models.review_output import ReviewOutput
    from app.services.event_publisher import EventPublisher

    publisher = EventPublisher(settings.REDIS_URL)

    try:
        async with async_session_factory() as db:
            # Load project
            result = await db.execute(
                select(Project).where(
                    Project.id == project_id, Project.deleted_at.is_(None)
                )
            )
            project = result.scalar_one_or_none()
            if not project:
                return {"error": f"Project {project_id} not found"}

            # Update status
            project.status = "updating"
            await db.flush()

            await publisher.publish(
                project_id, "progress", "update", {"phase": "updating"}
            )

            # Load existing papers
            result = await db.execute(
                select(ProjectPaper).where(
                    ProjectPaper.project_id == project_id,
                    ProjectPaper.deleted_at.is_(None),
                )
            )
            project_papers = result.scalars().all()
            existing_papers = []
            for pp in project_papers:
                p = pp.paper
                if p:
                    existing_papers.append({
                        "doi": p.doi,
                        "s2_id": p.s2_id,
                        "arxiv_id": p.arxiv_id,
                        "openalex_id": getattr(p, "openalex_id", None),
                        "pmid": getattr(p, "pmid", None),
                        "title": p.title,
                    })

            # Build state for update_node
            state = {
                "project_id": project_id,
                "user_query": project.user_query,
                "search_strategy": project.search_config or {},
                "selected_papers": existing_papers,
                "last_search_at": (
                    project.last_search_at.isoformat()
                    if project.last_search_at
                    else None
                ),
            }

            # Run Update Agent
            result_state = await update_node(state)

            # Persist update report as ReviewOutput
            new_papers = result_state.get("new_papers_found", [])
            report = result_state.get("update_report", "")

            output = ReviewOutput(
                project_id=project_id,
                output_type="update_report",
                content=report,
                structured_data={
                    "new_papers": new_papers,
                    "new_papers_count": len(new_papers),
                    "checked_at": result_state.get("last_search_at"),
                },
            )
            db.add(output)

            # Update project timestamp
            if result_state.get("last_search_at"):
                project.last_search_at = datetime.fromisoformat(
                    result_state["last_search_at"]
                )
            project.status = "completed"
            await db.commit()

            await publisher.publish(
                project_id,
                "complete",
                "update",
                {"new_papers_count": len(new_papers)},
            )

            return {
                "project_id": project_id,
                "new_papers_count": len(new_papers),
                "status": "update_complete",
            }

    except Exception as exc:
        await publisher.publish(
            project_id, "error", "update", {"message": str(exc)}
        )
        raise
    finally:
        await publisher.close()
