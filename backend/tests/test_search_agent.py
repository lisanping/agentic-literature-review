"""Tests for Search Agent — dedup, ranking, multi-source fetch, node function."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.agents.search_agent import (
    deduplicate_papers,
    multi_source_fetch,
    rank_papers,
    search_node,
)
from app.schemas.paper import PaperMetadata
from app.sources.base import PaperSource
from app.sources.registry import SourceRegistry


def _make_paper(**kwargs) -> PaperMetadata:
    defaults = {
        "title": "Test Paper",
        "authors": ["Author A"],
        "source": "semantic_scholar",
    }
    defaults.update(kwargs)
    return PaperMetadata(**defaults)


# ── Deduplication ──


def test_dedup_by_doi():
    papers = [
        _make_paper(title="Paper A", doi="10.1234/a"),
        _make_paper(title="Paper A copy", doi="10.1234/a"),
    ]
    result = deduplicate_papers(papers)
    assert len(result) == 1


def test_dedup_by_s2_id():
    papers = [
        _make_paper(title="Paper B", s2_id="s2-123"),
        _make_paper(title="Paper B dup", s2_id="s2-123"),
    ]
    result = deduplicate_papers(papers)
    assert len(result) == 1


def test_dedup_by_arxiv():
    papers = [
        _make_paper(title="Paper C", arxiv_id="2301.00001"),
        _make_paper(title="Paper C again", arxiv_id="2301.00001"),
    ]
    result = deduplicate_papers(papers)
    assert len(result) == 1


def test_dedup_by_title():
    papers = [
        _make_paper(title="Exact Same Title"),
        _make_paper(title="Exact Same Title"),
    ]
    result = deduplicate_papers(papers)
    assert len(result) == 1


def test_dedup_keeps_higher_citations():
    papers = [
        _make_paper(title="Paper", doi="10.1/x", citation_count=10),
        _make_paper(title="Paper", doi="10.1/x", citation_count=100),
    ]
    result = deduplicate_papers(papers)
    assert len(result) == 1
    assert result[0].citation_count == 100


def test_dedup_unique_papers():
    papers = [
        _make_paper(title="Paper A", doi="10.1/a"),
        _make_paper(title="Paper B", doi="10.1/b"),
        _make_paper(title="Paper C", doi="10.1/c"),
    ]
    result = deduplicate_papers(papers)
    assert len(result) == 3


# ── Ranking ──


def test_rank_papers_by_citations():
    papers = [
        _make_paper(title="Low Cited", citation_count=1),
        _make_paper(title="High Cited", citation_count=10000),
    ]
    ranked = rank_papers(papers)
    assert ranked[0].title == "High Cited"


def test_rank_papers_by_relevance():
    papers = [
        _make_paper(title="Unrelated Topic", abstract="Something about cooking"),
        _make_paper(title="LLM for Code", abstract="Large language models code generation"),
    ]
    ranked = rank_papers(papers, key_concepts=["LLM", "code generation"])
    assert ranked[0].title == "LLM for Code"


def test_rank_papers_empty():
    assert rank_papers([]) == []


# ── Multi-Source Fetch ──


@pytest.mark.asyncio
async def test_multi_source_fetch():
    paper = _make_paper(title="Found Paper")

    class FakeSource(PaperSource):
        async def search(self, query, filters=None):
            return [paper]
        async def get_paper(self, paper_id):
            return None
        async def get_citations(self, paper_id):
            return []
        async def get_references(self, paper_id):
            return []

    registry = SourceRegistry()
    registry.register("fake", FakeSource())

    results = await multi_source_fetch(registry, "test query")
    assert len(results) == 1
    assert results[0].title == "Found Paper"


@pytest.mark.asyncio
async def test_multi_source_fetch_handles_errors():
    class FailSource(PaperSource):
        async def search(self, query, filters=None):
            raise ConnectionError("API down")
        async def get_paper(self, paper_id):
            return None
        async def get_citations(self, paper_id):
            return []
        async def get_references(self, paper_id):
            return []

    class GoodSource(PaperSource):
        async def search(self, query, filters=None):
            return [_make_paper(title="OK")]
        async def get_paper(self, paper_id):
            return None
        async def get_citations(self, paper_id):
            return []
        async def get_references(self, paper_id):
            return []

    registry = SourceRegistry()
    registry.register("fail", FailSource())
    registry.register("good", GoodSource())

    results = await multi_source_fetch(registry, "test")
    assert len(results) == 1
    assert results[0].title == "OK"


# ── Search Node ──


@pytest.mark.asyncio
async def test_search_node():
    paper = _make_paper(title="Result Paper", s2_id="s2-abc")

    class FakeSource(PaperSource):
        async def search(self, query, filters=None):
            return [paper]
        async def get_paper(self, paper_id):
            return None
        async def get_citations(self, paper_id):
            return []
        async def get_references(self, paper_id):
            return []

    registry = SourceRegistry()
    registry.register("fake", FakeSource())

    state = {
        "user_query": "test query",
        "search_strategy": {
            "queries": [{"query": "test query", "purpose": "main"}],
            "key_concepts": ["test"],
            "suggested_filters": {},
        },
    }

    result = await search_node(state, source_registry=registry)

    assert "candidate_papers" in result
    assert len(result["candidate_papers"]) >= 1
    assert result["current_phase"] == "search_review"
    assert result["feedback_search_queries"] == []
