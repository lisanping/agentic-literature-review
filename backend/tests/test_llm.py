"""Tests for LLMRouter — model routing and token tracking."""

from unittest.mock import patch

from app.services.llm import (
    DEFAULT_MODEL_ROUTING,
    LLMRouter,
    ModelConfig,
    update_token_usage,
)


def _make_router(**kwargs):
    """Create a LLMRouter with mocked OpenAI client."""
    with patch("app.services.llm.AsyncOpenAI"):
        return LLMRouter(**kwargs)


def test_resolve_model_specific():
    """Should resolve to the model specified in the routing table."""
    router = _make_router()
    config = router.resolve_model("search", "query_planning")
    assert config.model_name == "gpt-4o-mini"


def test_resolve_model_default():
    """Should fall back to default model for unknown agent/task."""
    router = _make_router()
    config = router.resolve_model("unknown_agent", "unknown_task")
    assert config.model_name == "gpt-4o"


def test_resolve_writer_tasks():
    """Writer tasks should route to gpt-4o."""
    router = _make_router()
    for task in ["outline", "section_writing", "coherence_review"]:
        config = router.resolve_model("writer", task)
        assert config.model_name == "gpt-4o"


def test_resolve_reader_mixed():
    """Reader tasks use different models based on complexity."""
    router = _make_router()
    assert router.resolve_model("reader", "info_extraction").model_name == "gpt-4o"
    assert router.resolve_model("reader", "relation_detection").model_name == "gpt-4o-mini"


def test_custom_routing_table():
    """Should use custom routing table when provided."""
    custom_routing = {"search": {"query_planning": "gpt-4o"}}
    router = _make_router(routing_table=custom_routing)
    config = router.resolve_model("search", "query_planning")
    assert config.model_name == "gpt-4o"


def test_update_token_usage_new():
    """Should initialize usage when starting from None."""
    result = update_token_usage(None, "search", 100, 50)
    assert result["total_input"] == 100
    assert result["total_output"] == 50
    assert result["by_agent"]["search"]["input"] == 100
    assert result["by_agent"]["search"]["output"] == 50


def test_update_token_usage_accumulate():
    """Should accumulate across multiple calls."""
    usage = update_token_usage(None, "search", 100, 50)
    usage = update_token_usage(usage, "search", 200, 100)
    assert usage["total_input"] == 300
    assert usage["total_output"] == 150
    assert usage["by_agent"]["search"]["input"] == 300


def test_update_token_usage_multi_agent():
    """Should track per-agent usage separately."""
    usage = update_token_usage(None, "search", 100, 50)
    usage = update_token_usage(usage, "reader", 500, 200)
    assert usage["total_input"] == 600
    assert usage["by_agent"]["search"]["input"] == 100
    assert usage["by_agent"]["reader"]["input"] == 500
