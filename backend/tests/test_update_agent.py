"""Tests for Update Agent — incremental search, diff, relevance, report."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.update_agent import (
    assess_relevance,
    diff_papers,
    generate_update_report,
    update_node,
)


# ── Diff Tests ──


class TestDiffPapers:
    def test_removes_matching_doi(self):
        existing = [{"doi": "10.1234/a", "title": "Paper A"}]
        new_papers = [
            {"doi": "10.1234/a", "title": "Paper A"},
            {"doi": "10.1234/b", "title": "Paper B"},
        ]
        result = diff_papers(new_papers, existing)
        assert len(result) == 1
        assert result[0]["doi"] == "10.1234/b"

    def test_removes_matching_s2_id(self):
        existing = [{"s2_id": "abc123", "title": "X"}]
        new_papers = [{"s2_id": "abc123", "title": "X"}, {"s2_id": "def456", "title": "Y"}]
        result = diff_papers(new_papers, existing)
        assert len(result) == 1
        assert result[0]["s2_id"] == "def456"

    def test_removes_matching_openalex_id(self):
        existing = [{"openalex_id": "W123", "title": "X"}]
        new_papers = [{"openalex_id": "W123", "title": "X"}, {"openalex_id": "W456", "title": "Y"}]
        result = diff_papers(new_papers, existing)
        assert len(result) == 1
        assert result[0]["openalex_id"] == "W456"

    def test_removes_matching_pmid(self):
        existing = [{"pmid": "11111", "title": "X"}]
        new_papers = [{"pmid": "11111", "title": "X"}, {"pmid": "22222", "title": "Y"}]
        result = diff_papers(new_papers, existing)
        assert len(result) == 1
        assert result[0]["pmid"] == "22222"

    def test_removes_matching_title(self):
        existing = [{"title": "My Paper"}]
        new_papers = [{"title": "My Paper"}, {"title": "Different Paper"}]
        result = diff_papers(new_papers, existing)
        assert len(result) == 1
        assert result[0]["title"] == "Different Paper"

    def test_title_case_insensitive(self):
        existing = [{"title": "My Paper"}]
        new_papers = [{"title": "my paper"}]
        result = diff_papers(new_papers, existing)
        assert len(result) == 0

    def test_dedup_within_new(self):
        new_papers = [
            {"doi": "10.1234/a", "title": "Same"},
            {"doi": "10.1234/a", "title": "Same"},
        ]
        result = diff_papers(new_papers, [])
        assert len(result) == 1

    def test_empty_existing(self):
        new_papers = [{"title": "A"}, {"title": "B"}]
        result = diff_papers(new_papers, [])
        assert len(result) == 2

    def test_empty_new(self):
        existing = [{"title": "A"}]
        result = diff_papers([], existing)
        assert len(result) == 0


# ── Relevance Assessment Tests ──


class TestAssessRelevance:
    @pytest.mark.asyncio
    async def test_filters_by_threshold(self):
        papers = [
            {"title": "High Relevance", "abstract": "Very relevant content"},
            {"title": "Low Relevance", "abstract": "Not related at all"},
        ]

        mock_llm = AsyncMock()
        mock_llm.call.return_value = json.dumps([
            {"index": 1, "score": 9, "reason": "Highly relevant"},
            {"index": 2, "score": 2, "reason": "Not relevant"},
        ])

        mock_pm = MagicMock()
        mock_pm.render.return_value = "test prompt"

        result = await assess_relevance(
            papers, "test query", llm=mock_llm, prompt_manager=mock_pm
        )

        assert len(result) == 1
        assert result[0]["title"] == "High Relevance"
        assert result[0]["_relevance_score"] == 9

    @pytest.mark.asyncio
    async def test_empty_papers(self):
        result = await assess_relevance([], "test query")
        assert result == []

    @pytest.mark.asyncio
    async def test_parse_failure_fallback(self):
        papers = [{"title": "A", "abstract": "Text"}]

        mock_llm = AsyncMock()
        mock_llm.call.return_value = "not valid json"

        mock_pm = MagicMock()
        mock_pm.render.return_value = "prompt"

        result = await assess_relevance(
            papers, "q", llm=mock_llm, prompt_manager=mock_pm
        )

        # With fallback score 5 (below threshold 6), should be filtered
        assert len(result) == 0


# ── Report Generation Tests ──


class TestGenerateUpdateReport:
    @pytest.mark.asyncio
    async def test_generates_report(self):
        mock_llm = AsyncMock()
        mock_llm.call.return_value = "# Update Report\n\nNew findings..."

        mock_pm = MagicMock()
        mock_pm.render.return_value = "prompt"

        analyses = [{"title": "Paper A", "year": 2026, "findings": "Finding A"}]
        report = await generate_update_report(
            "test query", 10, analyses, llm=mock_llm, prompt_manager=mock_pm
        )

        assert len(report) > 0
        assert "Update Report" in report

    @pytest.mark.asyncio
    async def test_empty_analyses_returns_default(self):
        report = await generate_update_report("test", 10, [])
        assert "未发现" in report


# ── Full Node Tests ──


class TestUpdateNode:
    @pytest.mark.asyncio
    async def test_no_user_query(self):
        state = {"project_id": "test", "user_query": ""}
        result = await update_node(state)
        assert result["new_papers_found"] == []
        assert "缺少" in result["update_report"]

    @pytest.mark.asyncio
    async def test_no_new_papers(self):
        """When incremental search returns nothing."""
        mock_registry = MagicMock()
        mock_registry.get_enabled_sources.return_value = []

        state = {
            "project_id": "test",
            "user_query": "transformer attention",
            "search_strategy": {"queries": ["transformer"]},
            "selected_papers": [{"doi": "10.1/a", "title": "A"}],
        }

        result = await update_node(state, source_registry=mock_registry)
        assert result["new_papers_found"] == []
        assert "未发现" in result["update_report"]
        assert "last_search_at" in result

    @pytest.mark.asyncio
    async def test_full_update_flow(self):
        """Full flow: search → diff → assess → report."""
        # Mock source registry returning one new paper
        mock_source = AsyncMock()
        from app.schemas.paper import PaperMetadata

        mock_source.search.return_value = [
            PaperMetadata(
                title="Brand New Discovery",
                authors=["Author A"],
                year=2026,
                abstract="This is a new finding about transformers.",
                doi="10.9999/new",
                source="openalex",
            )
        ]

        mock_registry = MagicMock()
        mock_registry.get_enabled_sources.return_value = [("openalex", mock_source)]

        # Mock LLM
        mock_llm = AsyncMock()
        # First call: relevance assessment
        mock_llm.call.side_effect = [
            json.dumps([{"index": 1, "score": 9, "reason": "Highly relevant"}]),
            "# 更新报告\n\n发现了新的重要研究进展。",
        ]

        mock_pm = MagicMock()
        mock_pm.render.return_value = "prompt"

        state = {
            "project_id": "test",
            "user_query": "transformer attention mechanism",
            "search_strategy": {"queries": ["transformer attention"]},
            "selected_papers": [{"doi": "10.1/existing", "title": "Existing Paper"}],
            "last_search_at": "2025-01-01T00:00:00+00:00",
        }

        result = await update_node(
            state,
            source_registry=mock_registry,
            llm=mock_llm,
            prompt_manager=mock_pm,
        )

        assert len(result["new_papers_found"]) == 1
        assert result["new_papers_found"][0]["title"] == "Brand New Discovery"
        assert "更新报告" in result["update_report"]
        assert "last_search_at" in result
        assert result["current_phase"] == "updating"
