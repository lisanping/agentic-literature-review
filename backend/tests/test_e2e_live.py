"""End-to-end test with real LLM — requires OPENAI_API_KEY.

Run with:  pytest tests/test_e2e_live.py -m live

These tests are NOT run in CI. They verify the full pipeline
including actual LLM calls, Semantic Scholar API, etc.
"""

import os

import pytest

# Skip the entire module if no API key
pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.environ.get("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY not set — skipping live tests",
    ),
]


@pytest.mark.asyncio
async def test_live_intent_parsing():
    """Test intent parsing with real LLM."""
    from app.agents.intent_parser import parse_intent_node

    state = {
        "user_query": "What are the recent advances in large language models for code generation?",
        "output_language": "en",
    }
    result = await parse_intent_node(state)

    assert "search_strategy" in result
    strategy = result["search_strategy"]
    assert "queries" in strategy
    assert len(strategy["queries"]) > 0
    assert strategy["queries"][0]["query"]  # non-empty query string


@pytest.mark.asyncio
async def test_live_search_and_read():
    """Test search + read with real APIs and LLM."""
    from app.agents.intent_parser import parse_intent_node
    from app.agents.search_agent import search_node

    # Parse intent
    state = {
        "user_query": "transformer attention mechanism survey",
        "output_language": "en",
    }
    intent_result = await parse_intent_node(state)
    state.update(intent_result)

    # Search
    search_result = await search_node(state)
    state.update(search_result)

    candidates = state.get("candidate_papers", [])
    assert len(candidates) > 0, "Search should find at least some papers"

    # Verify candidate structure
    first = candidates[0]
    assert "title" in first
    assert "s2_id" in first or "arxiv_id" in first


@pytest.mark.asyncio
async def test_live_full_pipeline_quick():
    """Quick live test: intent → search only (no read/write to save tokens)."""
    from app.agents.intent_parser import parse_intent_node
    from app.agents.search_agent import search_node

    state = {
        "user_query": "few-shot learning in NLP",
        "output_language": "en",
        "output_types": ["quick_brief"],
    }

    result = await parse_intent_node(state)
    state.update(result)
    assert "search_strategy" in state

    result = await search_node(state)
    state.update(result)
    assert len(state.get("candidate_papers", [])) > 0
