"""Tests for parse_intent node."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.intent_parser import parse_intent_node, _parse_strategy_response


# ── _parse_strategy_response ──


def test_parse_strategy_clean_json():
    resp = json.dumps({
        "queries": [{"query": "LLM code gen", "purpose": "main"}],
        "key_concepts": ["LLM", "code"],
        "suggested_filters": {"year_min": 2020},
    })
    result = _parse_strategy_response(resp, "test query")
    assert len(result["queries"]) == 1
    assert result["key_concepts"] == ["LLM", "code"]


def test_parse_strategy_markdown_json():
    resp = '```json\n{"queries": [{"query": "test", "purpose": "x"}]}\n```'
    result = _parse_strategy_response(resp, "test query")
    assert len(result["queries"]) == 1


def test_parse_strategy_invalid_json():
    result = _parse_strategy_response("not json at all", "fallback query")
    assert len(result["queries"]) == 1
    assert result["queries"][0]["query"] == "fallback query"


def test_parse_strategy_no_queries_key():
    resp = json.dumps({"key_concepts": ["A"]})
    result = _parse_strategy_response(resp, "fallback")
    assert "queries" in result
    assert result["queries"][0]["query"] == "fallback"


# ── parse_intent_node ──


@pytest.mark.asyncio
async def test_parse_intent_node():
    mock_llm = MagicMock()
    mock_llm.call = AsyncMock(return_value=(
        json.dumps({
            "queries": [
                {"query": "large language models code generation", "purpose": "main"},
                {"query": "LLM program synthesis", "purpose": "synonym"},
            ],
            "key_concepts": ["LLM", "code generation", "program synthesis"],
            "suggested_filters": {"year_min": 2020},
        }),
        {"total_input": 100, "total_output": 50, "by_agent": {}},
    ))

    mock_pm = MagicMock()
    mock_pm.render.return_value = "test prompt"

    state = {
        "user_query": "LLM in code generation",
        "output_language": "zh",
    }

    result = await parse_intent_node(state, llm=mock_llm, prompt_manager=mock_pm)

    assert "search_strategy" in result
    assert len(result["search_strategy"]["queries"]) == 2
    assert result["current_phase"] == "searching"
    assert "token_usage" in result
    mock_llm.call.assert_called_once()
