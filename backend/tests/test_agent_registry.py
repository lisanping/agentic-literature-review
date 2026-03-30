"""Tests for ReviewState and AgentRegistry."""

import pytest

from app.agents.registry import AgentRegistry
from app.agents.state import ReviewState


def test_review_state_is_typed_dict():
    """ReviewState can be used as a dict."""
    state: ReviewState = {
        "user_query": "test",
        "output_language": "zh",
    }
    assert state["user_query"] == "test"


def test_registry_register_and_get():
    reg = AgentRegistry()

    def dummy_node(state):
        return {}

    reg.register("test", dummy_node)
    assert reg.get("test") is dummy_node


def test_registry_list_agents():
    reg = AgentRegistry()
    reg.register("a", lambda s: {})
    reg.register("b", lambda s: {})
    agents = reg.list_agents()
    assert "a" in agents
    assert "b" in agents


def test_registry_get_missing():
    reg = AgentRegistry()
    with pytest.raises(ValueError, match="not registered"):
        reg.get("nonexistent")


def test_global_registry_has_agents():
    """Verify agents self-register into the global registry."""
    # Import agents to trigger registration
    import app.agents.intent_parser  # noqa: F401
    import app.agents.search_agent  # noqa: F401
    import app.agents.reader_agent  # noqa: F401
    import app.agents.writer_agent  # noqa: F401
    import app.agents.verify_citations  # noqa: F401
    import app.agents.export_node  # noqa: F401
    from app.agents.registry import agent_registry

    agents = agent_registry.list_agents()
    assert "parse_intent" in agents
    assert "search" in agents
    assert "read" in agents
    assert "generate_outline" in agents
    assert "write_review" in agents
    assert "revise_review" in agents
    assert "verify_citations" in agents
    assert "export" in agents
