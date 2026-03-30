"""Pydantic schemas for Project — request/response models."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import CitationStyle, OutputType, ProjectStatus


class ProjectCreate(BaseModel):
    """Create project request."""

    user_query: str = Field(..., min_length=2, max_length=2000)
    output_types: list[OutputType] = Field(default=[OutputType.FULL_REVIEW])
    output_language: str = Field(default="zh", pattern=r"^(zh|en|bilingual)$")
    citation_style: CitationStyle = Field(default=CitationStyle.APA)
    search_config: dict | None = None
    token_budget: int | None = None


class ProjectUpdate(BaseModel):
    """Update project request (partial)."""

    title: str | None = None
    output_types: list[OutputType] | None = None
    output_language: str | None = Field(
        default=None, pattern=r"^(zh|en|bilingual)$"
    )
    citation_style: CitationStyle | None = None
    search_config: dict | None = None
    token_budget: int | None = None


class ProjectResponse(BaseModel):
    """Project detail response."""

    model_config = {"from_attributes": True}

    id: str
    user_id: str | None
    title: str
    user_query: str
    status: ProjectStatus
    output_types: list[OutputType]
    output_language: str
    citation_style: CitationStyle
    paper_count: int
    token_usage: dict | None
    token_budget: int | None
    created_at: datetime
    updated_at: datetime
