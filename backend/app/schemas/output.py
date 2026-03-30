"""Pydantic schemas for ReviewOutput — request/response models."""

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import CitationStyle, OutputType


class ReviewOutputResponse(BaseModel):
    """Review output detail response."""

    model_config = {"from_attributes": True}

    id: str
    project_id: str
    output_type: OutputType
    title: str | None
    outline: dict | None
    content: str | None
    structured_data: dict | None
    references: list[dict] | None
    version: int
    language: str
    citation_style: CitationStyle
    writing_style: str | None
    citation_verification: list[dict] | None
    export_formats: list[str] | None
    created_at: datetime
    updated_at: datetime


class PaginatedResponse(BaseModel):
    """Unified paginated response wrapper."""

    items: list
    total: int
    page: int
    size: int
    pages: int
