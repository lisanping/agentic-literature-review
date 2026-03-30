"""Tests for ORM models — CRUD operations on all tables."""

import pytest
from sqlalchemy import select

from app.models.paper import Paper, PaperFulltext
from app.models.paper_analysis import PaperAnalysis
from app.models.project import Project
from app.models.project_paper import ProjectPaper
from app.models.review_output import ReviewOutput


# ── Project CRUD ──


@pytest.mark.asyncio
async def test_create_project(db_session):
    project = Project(
        title="Test Review",
        user_query="LLM in code generation",
        status="created",
        output_types=["full_review"],
        output_language="en",
        citation_style="apa",
    )
    db_session.add(project)
    await db_session.commit()

    result = await db_session.execute(
        select(Project).where(Project.id == project.id)
    )
    fetched = result.scalar_one()
    assert fetched.title == "Test Review"
    assert fetched.user_query == "LLM in code generation"
    assert fetched.status == "created"
    assert fetched.output_types == ["full_review"]
    assert fetched.paper_count == 0
    assert fetched.deleted_at is None


@pytest.mark.asyncio
async def test_update_project(db_session):
    project = Project(title="Old Title", user_query="q")
    db_session.add(project)
    await db_session.commit()

    project.title = "New Title"
    project.status = "searching"
    await db_session.commit()

    result = await db_session.execute(
        select(Project).where(Project.id == project.id)
    )
    fetched = result.scalar_one()
    assert fetched.title == "New Title"
    assert fetched.status == "searching"


@pytest.mark.asyncio
async def test_soft_delete_project(db_session):
    from datetime import datetime, timezone

    project = Project(title="To Delete", user_query="q")
    db_session.add(project)
    await db_session.commit()

    project.deleted_at = datetime.now(timezone.utc)
    await db_session.commit()

    result = await db_session.execute(
        select(Project).where(Project.id == project.id)
    )
    fetched = result.scalar_one()
    assert fetched.deleted_at is not None


# ── Paper CRUD ──


@pytest.mark.asyncio
async def test_create_paper(db_session):
    paper = Paper(
        title="Attention Is All You Need",
        authors=["Vaswani, A.", "Shazeer, N."],
        year=2017,
        venue="NeurIPS",
        abstract="We propose the Transformer...",
        doi="10.5555/3295222.3295349",
        source="semantic_scholar",
        citation_count=80000,
    )
    db_session.add(paper)
    await db_session.commit()

    result = await db_session.execute(
        select(Paper).where(Paper.doi == "10.5555/3295222.3295349")
    )
    fetched = result.scalar_one()
    assert fetched.title == "Attention Is All You Need"
    assert fetched.authors == ["Vaswani, A.", "Shazeer, N."]
    assert fetched.year == 2017
    assert fetched.citation_count == 80000


@pytest.mark.asyncio
async def test_paper_fulltext(db_session):
    paper = Paper(
        title="Test Paper",
        authors=["Author A"],
        source="arxiv",
    )
    db_session.add(paper)
    await db_session.flush()

    fulltext = PaperFulltext(
        paper_id=paper.id,
        content="Full text content of the paper...",
        parser_used="pymupdf",
    )
    db_session.add(fulltext)
    await db_session.commit()

    result = await db_session.execute(
        select(PaperFulltext).where(PaperFulltext.paper_id == paper.id)
    )
    fetched = result.scalar_one()
    assert fetched.content == "Full text content of the paper..."
    assert fetched.parser_used == "pymupdf"


@pytest.mark.asyncio
async def test_paper_unique_doi(db_session):
    """Two papers with the same DOI should conflict."""
    from sqlalchemy.exc import IntegrityError

    p1 = Paper(title="Paper A", authors=["A"], source="arxiv", doi="10.1234/test")
    db_session.add(p1)
    await db_session.flush()

    p2 = Paper(title="Paper B", authors=["B"], source="arxiv", doi="10.1234/test")
    db_session.add(p2)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


# ── ProjectPaper ──


@pytest.mark.asyncio
async def test_project_paper_association(db_session):
    project = Project(title="My Review", user_query="q")
    paper = Paper(title="A Paper", authors=["X"], source="arxiv")
    db_session.add_all([project, paper])
    await db_session.flush()

    pp = ProjectPaper(
        project_id=project.id,
        paper_id=paper.id,
        status="candidate",
        found_by="search",
        relevance_rank=1,
    )
    db_session.add(pp)
    await db_session.commit()

    result = await db_session.execute(
        select(ProjectPaper).where(ProjectPaper.project_id == project.id)
    )
    fetched = result.scalar_one()
    assert fetched.status == "candidate"
    assert fetched.found_by == "search"
    assert fetched.relevance_rank == 1


@pytest.mark.asyncio
async def test_project_paper_status_update(db_session):
    project = Project(title="Review", user_query="q")
    paper = Paper(title="Paper", authors=["A"], source="arxiv")
    db_session.add_all([project, paper])
    await db_session.flush()

    pp = ProjectPaper(
        project_id=project.id, paper_id=paper.id, status="candidate"
    )
    db_session.add(pp)
    await db_session.commit()

    pp.status = "selected"
    await db_session.commit()

    result = await db_session.execute(
        select(ProjectPaper).where(ProjectPaper.id == pp.id)
    )
    assert result.scalar_one().status == "selected"


# ── PaperAnalysis ──


@pytest.mark.asyncio
async def test_create_paper_analysis(db_session):
    project = Project(title="Review", user_query="q")
    paper = Paper(title="Paper", authors=["A"], source="arxiv")
    db_session.add_all([project, paper])
    await db_session.flush()

    analysis = PaperAnalysis(
        project_id=project.id,
        paper_id=paper.id,
        objective="Study X",
        methodology="Method Y",
        datasets=["dataset1", "dataset2"],
        findings="Found Z",
        limitations="Limited by W",
        key_concepts=["concept1", "concept2"],
        relations=[],
        relevance_score=0.85,
        analysis_depth="fulltext",
        model_used="gpt-4o",
    )
    db_session.add(analysis)
    await db_session.commit()

    result = await db_session.execute(
        select(PaperAnalysis).where(PaperAnalysis.project_id == project.id)
    )
    fetched = result.scalar_one()
    assert fetched.objective == "Study X"
    assert fetched.datasets == ["dataset1", "dataset2"]
    assert fetched.relevance_score == 0.85
    assert fetched.analysis_depth == "fulltext"


# ── ReviewOutput ──


@pytest.mark.asyncio
async def test_create_review_output(db_session):
    project = Project(title="Review", user_query="q")
    db_session.add(project)
    await db_session.flush()

    output = ReviewOutput(
        project_id=project.id,
        output_type="full_review",
        title="Literature Review on LLM",
        content="# Introduction\n\nThis review...",
        references=[{"title": "Paper A", "year": 2024}],
        language="en",
        citation_style="apa",
        writing_style="narrative",
    )
    db_session.add(output)
    await db_session.commit()

    result = await db_session.execute(
        select(ReviewOutput).where(ReviewOutput.project_id == project.id)
    )
    fetched = result.scalar_one()
    assert fetched.output_type == "full_review"
    assert fetched.version == 1
    assert "Introduction" in fetched.content
    assert len(fetched.references) == 1


@pytest.mark.asyncio
async def test_review_output_versioning(db_session):
    project = Project(title="Review", user_query="q")
    db_session.add(project)
    await db_session.flush()

    v1 = ReviewOutput(
        project_id=project.id,
        output_type="full_review",
        content="Draft v1",
        version=1,
    )
    db_session.add(v1)
    await db_session.flush()

    v2 = ReviewOutput(
        project_id=project.id,
        output_type="full_review",
        content="Draft v2 — improved",
        version=2,
        parent_id=v1.id,
        revision_notes="Improved introduction",
    )
    db_session.add(v2)
    await db_session.commit()

    result = await db_session.execute(
        select(ReviewOutput)
        .where(ReviewOutput.project_id == project.id)
        .order_by(ReviewOutput.version)
    )
    outputs = result.scalars().all()
    assert len(outputs) == 2
    assert outputs[1].parent_id == outputs[0].id
    assert outputs[1].revision_notes == "Improved introduction"
