"""Tests for paper deduplication logic."""

import pytest

from app.models.paper import Paper
from app.schemas.paper import PaperMetadata
from app.services.paper_ops import (
    find_or_create_paper,
    normalize_title,
    title_similarity,
)


# ── normalize_title ──


def test_normalize_title_basic():
    assert normalize_title("Hello World!") == "hello world"


def test_normalize_title_unicode():
    assert normalize_title("Résumé of Naïve Approaches") == "resume of naive approaches"


def test_normalize_title_extra_spaces():
    assert normalize_title("  lots   of    spaces  ") == "lots of spaces"


def test_normalize_title_punctuation():
    assert normalize_title("A Title: With — Punctuation!?") == "a title with punctuation"


# ── title_similarity ──


def test_title_similarity_identical():
    assert title_similarity("Attention Is All You Need", "Attention Is All You Need") == 1.0


def test_title_similarity_case_insensitive():
    assert title_similarity("attention is all you need", "ATTENTION IS ALL YOU NEED") == 1.0


def test_title_similarity_different():
    score = title_similarity("Attention Is All You Need", "BERT: Pre-training")
    assert score < 0.5


def test_title_similarity_high_overlap():
    score = title_similarity(
        "Attention Is All You Need",
        "Attention Is All We Need",
    )
    assert score > 0.6


def test_title_similarity_empty():
    assert title_similarity("", "") == 0.0


# ── find_or_create_paper ──


@pytest.mark.asyncio
async def test_dedup_by_doi(db_session):
    """Should find existing paper by DOI."""
    existing = Paper(
        title="Paper A", authors=["Auth"], source="arxiv", doi="10.1234/test"
    )
    db_session.add(existing)
    await db_session.flush()

    metadata = PaperMetadata(
        title="Paper A (different casing)",
        authors=["Auth"],
        source="semantic_scholar",
        doi="10.1234/test",
        abstract="Added abstract",
    )
    result = await find_or_create_paper(db_session, metadata)
    assert result.id == existing.id
    assert result.abstract == "Added abstract"  # merged


@pytest.mark.asyncio
async def test_dedup_by_s2_id(db_session):
    """Should find existing paper by Semantic Scholar ID."""
    existing = Paper(
        title="Paper B", authors=["Auth"], source="semantic_scholar", s2_id="abc123"
    )
    db_session.add(existing)
    await db_session.flush()

    metadata = PaperMetadata(
        title="Paper B",
        authors=["Auth"],
        source="arxiv",
        s2_id="abc123",
        pdf_url="https://example.com/paper.pdf",
    )
    result = await find_or_create_paper(db_session, metadata)
    assert result.id == existing.id
    assert result.pdf_url == "https://example.com/paper.pdf"


@pytest.mark.asyncio
async def test_dedup_by_arxiv_id(db_session):
    """Should find existing paper by arXiv ID."""
    existing = Paper(
        title="Paper C", authors=["Auth"], source="arxiv", arxiv_id="2301.00001"
    )
    db_session.add(existing)
    await db_session.flush()

    metadata = PaperMetadata(
        title="Paper C",
        authors=["Auth"],
        source="semantic_scholar",
        arxiv_id="2301.00001",
    )
    result = await find_or_create_paper(db_session, metadata)
    assert result.id == existing.id


@pytest.mark.asyncio
async def test_dedup_by_title_similarity(db_session):
    """Should find existing paper by title fuzzy match."""
    existing = Paper(
        title="Attention Is All You Need",
        authors=["Vaswani"],
        source="semantic_scholar",
    )
    db_session.add(existing)
    await db_session.flush()

    metadata = PaperMetadata(
        title="Attention is All You Need",  # different casing
        authors=["Vaswani"],
        source="arxiv",
    )
    result = await find_or_create_paper(db_session, metadata)
    assert result.id == existing.id


@pytest.mark.asyncio
async def test_create_new_paper(db_session):
    """Should create a new paper when no match found."""
    metadata = PaperMetadata(
        title="A Completely New Paper",
        authors=["New Author"],
        year=2026,
        source="arxiv",
        doi="10.9999/new",
    )
    result = await find_or_create_paper(db_session, metadata)
    assert result.id is not None
    assert result.title == "A Completely New Paper"
    assert result.doi == "10.9999/new"


@pytest.mark.asyncio
async def test_merge_fills_missing_fields(db_session):
    """Merge should fill missing fields without overwriting existing ones."""
    existing = Paper(
        title="Test Paper",
        authors=["A"],
        source="arxiv",
        arxiv_id="2301.00001",
        citation_count=10,
    )
    db_session.add(existing)
    await db_session.flush()

    metadata = PaperMetadata(
        title="Test Paper",
        authors=["A"],
        source="semantic_scholar",
        arxiv_id="2301.00001",
        doi="10.1234/merged",
        s2_id="s2-xyz",
        citation_count=50,
        venue="NeurIPS",
        abstract="An abstract",
    )
    result = await find_or_create_paper(db_session, metadata)
    assert result.id == existing.id
    assert result.doi == "10.1234/merged"      # filled
    assert result.s2_id == "s2-xyz"            # filled
    assert result.venue == "NeurIPS"           # filled
    assert result.abstract == "An abstract"    # filled
    assert result.citation_count == 50         # updated (higher)
