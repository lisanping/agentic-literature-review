"""Tests for verify_citations and export nodes."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.agents.verify_citations import verify_citations_node
from app.agents.export_node import export_node
from app.schemas.paper import PaperMetadata
from app.sources.base import PaperSource
from app.sources.registry import SourceRegistry


# ── FakeSource for verify_citations ──


class FakeS2Source(PaperSource):
    """Fake S2 source that verifies papers by ID prefix."""

    def __init__(self, known_ids: set[str] | None = None):
        self.known_ids = known_ids or set()

    async def search(self, query, filters=None):
        return []

    async def get_paper(self, paper_id):
        if paper_id in self.known_ids:
            return PaperMetadata(
                title="Verified Paper",
                authors=["Author"],
                source="semantic_scholar",
            )
        return None

    async def get_citations(self, paper_id):
        return []

    async def get_references(self, paper_id):
        return []


# ── verify_citations_node ──


@pytest.mark.asyncio
async def test_verify_citations_all_verified():
    registry = SourceRegistry()
    registry.register("semantic_scholar", FakeS2Source(known_ids={"s2-1", "s2-2"}))

    state = {
        "references": [
            {"paper_id": "s2-1", "title": "Paper A"},
            {"paper_id": "s2-2", "title": "Paper B"},
        ],
    }

    result = await verify_citations_node(state, source_registry=registry)
    assert len(result["citation_verification"]) == 2
    assert all(v["status"] == "verified" for v in result["citation_verification"])


@pytest.mark.asyncio
async def test_verify_citations_some_unverified():
    registry = SourceRegistry()
    registry.register("semantic_scholar", FakeS2Source(known_ids={"s2-1"}))

    state = {
        "references": [
            {"paper_id": "s2-1", "title": "Paper A"},
            {"paper_id": "s2-unknown", "title": "Paper B"},
        ],
    }

    result = await verify_citations_node(state, source_registry=registry)
    statuses = {v["paper_id"]: v["status"] for v in result["citation_verification"]}
    assert statuses["s2-1"] == "verified"
    assert statuses["s2-unknown"] == "unverified"


@pytest.mark.asyncio
async def test_verify_citations_empty():
    state = {"references": []}
    result = await verify_citations_node(state)
    assert result["citation_verification"] == []


@pytest.mark.asyncio
async def test_verify_citations_by_doi():
    """Should try DOI lookup if paper_id fails."""
    registry = SourceRegistry()
    registry.register("semantic_scholar", FakeS2Source(known_ids={"DOI:10.1234/test"}))

    state = {
        "references": [
            {"paper_id": "unknown", "title": "Paper", "doi": "10.1234/test"},
        ],
    }

    result = await verify_citations_node(state, source_registry=registry)
    assert result["citation_verification"][0]["status"] == "verified"


# ── export_node ──


@pytest.mark.asyncio
async def test_export_node():
    state = {
        "full_draft": "# My Review\n\nContent here.",
        "references": [
            {"title": "Paper A", "formatted": "Author (2024). Paper A."},
        ],
        "outline": {"title": "My Review"},
    }

    result = await export_node(state)
    assert "final_output" in result
    assert "My Review" in result["final_output"]
    assert result["current_phase"] == "completed"


@pytest.mark.asyncio
async def test_export_node_empty():
    state = {"full_draft": "", "references": [], "outline": {}}
    result = await export_node(state)
    assert "final_output" in result
    assert result["current_phase"] == "completed"
