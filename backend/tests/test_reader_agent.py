"""Tests for Reader Agent — info extraction, process_single_paper, read_node."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.reader_agent import (
    _parse_extraction_response,
    process_single_paper,
    read_node,
    read_papers_parallel,
)


# ── _parse_extraction_response ──


def test_parse_extraction_clean_json():
    resp = json.dumps({
        "objective": "Study X",
        "methodology": "Method Y",
        "datasets": ["DS1"],
        "findings": "Found Z",
        "limitations": "Limited W",
        "key_concepts": ["A", "B"],
        "method_category": "deep_learning",
    })
    result = _parse_extraction_response(resp)
    assert result["objective"] == "Study X"
    assert result["methodology"] == "Method Y"
    assert result["datasets"] == ["DS1"]
    assert result["key_concepts"] == ["A", "B"]


def test_parse_extraction_markdown_json():
    resp = '```json\n{"objective": "Test", "method": "M"}\n```'
    result = _parse_extraction_response(resp)
    assert result["objective"] == "Test"
    assert result["methodology"] == "M"


def test_parse_extraction_invalid():
    result = _parse_extraction_response("not json")
    assert result["objective"] is None
    assert result["datasets"] == []


# ── process_single_paper ──


@pytest.mark.asyncio
async def test_process_single_paper_abstract_only():
    """Paper without PDF should fall back to abstract analysis."""
    mock_llm = MagicMock()
    mock_llm.call = AsyncMock(return_value=(
        json.dumps({
            "objective": "Test objective",
            "methodology": "Test method",
            "datasets": [],
            "findings": "Test findings",
            "limitations": "None",
            "key_concepts": ["concept"],
            "method_category": "ml",
        }),
        {"total_input": 50, "total_output": 30, "by_agent": {}},
    ))
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    paper = {
        "title": "Test Paper",
        "authors": ["Author A"],
        "abstract": "This paper studies...",
        "s2_id": "s2-123",
        "open_access": False,
    }

    result = await process_single_paper(paper, "test query", mock_llm, mock_pm)
    assert result["paper_id"] == "s2-123"
    assert result["analysis_depth"] == "abstract_only"
    assert result["objective"] == "Test objective"


# ── read_papers_parallel ──


@pytest.mark.asyncio
async def test_read_papers_parallel():
    mock_llm = MagicMock()
    mock_llm.call = AsyncMock(return_value=(
        json.dumps({
            "objective": "Obj",
            "methodology": "Meth",
            "datasets": [],
            "findings": "Find",
            "limitations": "Lim",
            "key_concepts": [],
            "method_category": "test",
        }),
        {"total_input": 50, "total_output": 30, "by_agent": {}},
    ))
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    papers = [
        {"title": f"Paper {i}", "authors": ["A"], "abstract": "Abstract", "s2_id": f"s2-{i}"}
        for i in range(3)
    ]

    results, usage = await read_papers_parallel(
        papers, "query", mock_llm, mock_pm, max_concurrent=2
    )
    assert len(results) == 3
    assert all(r["objective"] == "Obj" for r in results)


# ── read_node ──


@pytest.mark.asyncio
async def test_read_node():
    mock_llm = MagicMock()
    mock_llm.call = AsyncMock(return_value=(
        json.dumps({
            "objective": "Study X",
            "methodology": "Method Y",
            "datasets": ["DS"],
            "findings": "Found Z",
            "limitations": "None",
            "key_concepts": ["concept"],
            "method_category": "cat",
        }),
        {"total_input": 50, "total_output": 30, "by_agent": {}},
    ))
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    state = {
        "user_query": "test query",
        "selected_papers": [
            {"title": "Paper A", "authors": ["X"], "abstract": "Abs", "s2_id": "s2-1"},
            {"title": "Paper B", "authors": ["Y"], "abstract": "Abs", "s2_id": "s2-2"},
        ],
    }

    result = await read_node(state, llm=mock_llm, prompt_manager=mock_pm)

    assert len(result["paper_analyses"]) == 2
    assert result["reading_progress"]["completed"] == 2
    assert result["fulltext_coverage"]["abstract_only_count"] == 2
    assert result["current_phase"] == "outlining"


@pytest.mark.asyncio
async def test_read_node_empty():
    mock_llm = MagicMock()
    state = {"user_query": "test", "selected_papers": []}
    result = await read_node(state, llm=mock_llm)
    assert result["paper_analyses"] == []
