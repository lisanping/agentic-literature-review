"""Tests for Writer Agent — outline, section writing, references, coherence."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.agents.writer_agent import (
    build_references_list,
    generate_outline_node,
    revise_review_node,
    write_review_node,
    _parse_json_response,
)


# ── _parse_json_response ──


def test_parse_json_clean():
    result = _parse_json_response('{"key": "value"}', {"fallback": True})
    assert result == {"key": "value"}


def test_parse_json_markdown():
    result = _parse_json_response('```json\n{"key": "v"}\n```', {})
    assert result == {"key": "v"}


def test_parse_json_invalid():
    result = _parse_json_response("not json", {"fallback": True})
    assert result == {"fallback": True}


# ── build_references_list ──


def test_build_references_list():
    analyses = [
        {"title": "Paper A", "authors": ["Author A"], "year": 2024, "paper_id": "p1"},
        {"title": "Paper B", "authors": ["Author B"], "year": 2023, "paper_id": "p2"},
    ]
    refs = build_references_list(analyses, "apa")
    assert len(refs) == 2
    assert refs[0]["index"] == 1
    assert refs[0]["title"] == "Paper A"
    assert "Paper A" in refs[0]["formatted"]
    assert "2024" in refs[0]["formatted"]


def test_build_references_list_empty():
    assert build_references_list([], "apa") == []


# ── generate_outline_node ──


@pytest.mark.asyncio
async def test_generate_outline_node():
    mock_llm = MagicMock()
    mock_llm.call = AsyncMock(return_value=(
        json.dumps({
            "title": "Review of LLM",
            "sections": [
                {"heading": "Introduction", "description": "Background", "subsections": [], "relevant_paper_indices": []},
                {"heading": "Methods", "description": "Approaches", "subsections": [], "relevant_paper_indices": [1, 2]},
                {"heading": "Conclusion", "description": "Summary", "subsections": [], "relevant_paper_indices": []},
            ],
        }),
        {"total_input": 200, "total_output": 100, "by_agent": {}},
    ))
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    state = {
        "user_query": "LLM in code generation",
        "paper_analyses": [
            {"title": "Paper 1", "objective": "Obj1"},
            {"title": "Paper 2", "objective": "Obj2"},
        ],
        "output_types": ["full_review"],
        "output_language": "zh",
    }

    result = await generate_outline_node(state, llm=mock_llm, prompt_manager=mock_pm)

    assert "outline" in result
    assert result["outline"]["title"] == "Review of LLM"
    assert len(result["outline"]["sections"]) == 3
    assert result["current_phase"] == "outline_review"


# ── write_review_node ──


@pytest.mark.asyncio
async def test_write_review_node():
    call_count = 0

    async def mock_call(prompt, agent_name, task_type, token_usage=None, **kw):
        nonlocal call_count
        call_count += 1
        return f"Section {call_count} content about the topic.", {
            "total_input": 100 * call_count,
            "total_output": 50 * call_count,
            "by_agent": {},
        }

    mock_llm = MagicMock()
    mock_llm.call = AsyncMock(side_effect=mock_call)
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    state = {
        "user_query": "test query",
        "outline": {
            "title": "Test Review",
            "sections": [
                {"heading": "Intro", "description": "Background", "relevant_paper_indices": [1]},
                {"heading": "Main", "description": "Key findings", "relevant_paper_indices": [1, 2]},
            ],
        },
        "paper_analyses": [
            {"title": "P1", "paper_id": "1", "objective": "O1", "authors": ["A"], "year": 2024},
            {"title": "P2", "paper_id": "2", "objective": "O2", "authors": ["B"], "year": 2023},
        ],
        "citation_style": "apa",
        "output_language": "zh",
    }

    result = await write_review_node(state, llm=mock_llm, prompt_manager=mock_pm)

    assert "full_draft" in result
    assert "# Test Review" in result["full_draft"]
    assert len(result["draft_sections"]) == 2
    assert len(result["references"]) == 2
    assert result["current_phase"] == "draft_review"


# ── revise_review_node ──


@pytest.mark.asyncio
async def test_revise_review_node():
    mock_llm = MagicMock()
    mock_llm.call = AsyncMock(return_value=(
        "# Revised Review\n\nImproved content here.",
        {"total_input": 500, "total_output": 300, "by_agent": {}},
    ))
    mock_pm = MagicMock()

    state = {
        "user_query": "test",
        "full_draft": "# Original Draft\n\nOld content.",
        "revision_instructions": "Please improve the introduction.",
    }

    result = await revise_review_node(state, llm=mock_llm, prompt_manager=mock_pm)

    assert "Revised Review" in result["full_draft"]
    assert result["revision_instructions"] == ""
