"""Pydantic schemas for workflow control — HitlFeedback + responses — §8.3.2."""

from pydantic import BaseModel, Field


class HitlFeedback(BaseModel):
    """User feedback submitted at an HITL interrupt node."""

    hitl_type: str = Field(
        ...,
        pattern=r"^(search_review|outline_review|draft_review)$",
        description="Type of HITL node",
    )

    # ── Search review ──
    selected_paper_ids: list[str] | None = None
    additional_query: str | None = None

    # ── Outline review ──
    approved_outline: dict | None = None

    # ── Draft review ──
    revision_instructions: str | None = None

    approved: bool = True


class WorkflowStartResponse(BaseModel):
    """Response after starting/resuming a workflow."""

    task_id: str
    status: str


class WorkflowStatusResponse(BaseModel):
    """Current workflow status."""

    project_id: str
    phase: str | None
    status: str
    progress: dict | None = None
    token_usage: dict | None = None


class ExportRequest(BaseModel):
    """Export format request."""

    format: str = Field(
        ...,
        pattern=r"^(markdown|word|bibtex|ris)$",
        description="Export format",
    )
