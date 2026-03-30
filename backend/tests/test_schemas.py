"""Tests for Pydantic schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.schemas.paper import PaperMetadata, PaperResponse
from app.schemas.output import ReviewOutputResponse, PaginatedResponse


# ── ProjectCreate ──


def test_project_create_minimal():
    p = ProjectCreate(user_query="LLM in code generation")
    assert p.user_query == "LLM in code generation"
    assert p.output_types == ["full_review"]
    assert p.output_language == "zh"
    assert p.citation_style == "apa"


def test_project_create_full():
    p = ProjectCreate(
        user_query="Deep learning in medical imaging",
        output_types=["quick_brief", "annotated_bib"],
        output_language="en",
        citation_style="ieee",
        token_budget=500000,
    )
    assert len(p.output_types) == 2
    assert p.token_budget == 500000


def test_project_create_too_short():
    with pytest.raises(ValidationError):
        ProjectCreate(user_query="x")  # min_length=2


def test_project_create_invalid_language():
    with pytest.raises(ValidationError):
        ProjectCreate(user_query="test", output_language="fr")


# ── ProjectUpdate ──


def test_project_update_partial():
    u = ProjectUpdate(title="New Title")
    assert u.title == "New Title"
    assert u.output_types is None


# ── PaperMetadata ──


def test_paper_metadata_minimal():
    m = PaperMetadata(
        title="A Paper",
        authors=["Author A"],
        source="arxiv",
    )
    assert m.citation_count == 0
    assert m.open_access is False
    assert m.doi is None


def test_paper_metadata_full():
    m = PaperMetadata(
        title="Paper",
        authors=["A", "B"],
        year=2024,
        venue="NeurIPS",
        abstract="An abstract",
        doi="10.1234/test",
        s2_id="s2abc",
        arxiv_id="2401.00001",
        citation_count=100,
        reference_count=30,
        source="semantic_scholar",
        source_url="https://example.com",
        pdf_url="https://example.com/paper.pdf",
        open_access=True,
    )
    assert m.doi == "10.1234/test"
    assert m.open_access is True


# ── PaginatedResponse ──


def test_paginated_response():
    p = PaginatedResponse(
        items=[{"id": "1"}, {"id": "2"}],
        total=10,
        page=1,
        size=2,
        pages=5,
    )
    assert len(p.items) == 2
    assert p.pages == 5
