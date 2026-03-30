"""Tests for the orchestration layer — routing, graph building, HITL, feedback loops."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver

from app.agents.routing import (
    MAX_FEEDBACK_ITERATIONS,
    check_token_budget,
    route_after_draft_review,
    route_after_read,
    route_after_search_review,
    route_after_critique,
    ROUTER_REGISTRY,
)
from app.agents.orchestrator import (
    build_review_graph,
    check_read_feedback,
    check_critic_feedback,
    compile_review_graph,
    human_review_draft,
    human_review_outline,
    human_review_search,
    load_workflow_config,
)
from app.agents.state import ReviewState


# ═══════════════════════════════════════════════
#  Routing function tests
# ═══════════════════════════════════════════════


class TestRouteAfterSearchReview:
    def test_needs_more_search(self):
        state = {"needs_more_search": True, "selected_papers": [{"id": 1}]}
        assert route_after_search_review(state) == "search"

    def test_no_selected_papers(self):
        state = {"selected_papers": []}
        assert route_after_search_review(state) == "search"

    def test_normal_to_read(self):
        state = {"selected_papers": [{"id": 1}]}
        assert route_after_search_review(state) == "read"


class TestRouteAfterRead:
    def test_feedback_within_limit(self):
        state = {
            "feedback_search_queries": ["extra query"],
            "feedback_iteration_count": 0,
        }
        assert route_after_read(state) == "search"

    def test_feedback_at_limit(self):
        state = {
            "feedback_search_queries": ["query"],
            "feedback_iteration_count": MAX_FEEDBACK_ITERATIONS,
        }
        assert route_after_read(state) == "analyze"

    def test_no_feedback(self):
        state = {"feedback_search_queries": [], "feedback_iteration_count": 0}
        assert route_after_read(state) == "analyze"

    def test_empty_queries(self):
        state = {}
        assert route_after_read(state) == "analyze"


class TestRouteAfterCritique:
    def test_feedback(self):
        state = {"feedback_search_queries": ["gap"], "feedback_iteration_count": 0}
        assert route_after_critique(state) == "search"

    def test_no_feedback(self):
        state = {}
        assert route_after_critique(state) == "generate_outline"


class TestRouteAfterDraftReview:
    def test_revision_needed(self):
        state = {"revision_instructions": "Fix intro."}
        assert route_after_draft_review(state) == "revise_review"

    def test_no_revision(self):
        state = {}
        assert route_after_draft_review(state) == "export"

    def test_empty_revision(self):
        state = {"revision_instructions": ""}
        assert route_after_draft_review(state) == "export"


class TestCheckTokenBudget:
    def test_no_budget(self):
        state = {"token_budget": None}
        assert check_token_budget(state) == "continue"

    def test_within_budget(self):
        state = {
            "token_budget": 10000,
            "token_usage": {"total_input": 3000, "total_output": 2000},
        }
        assert check_token_budget(state) == "continue"

    def test_exceeded(self):
        state = {
            "token_budget": 5000,
            "token_usage": {"total_input": 3000, "total_output": 3000},
        }
        assert check_token_budget(state) == "budget_exceeded"


def test_router_registry_completeness():
    for name in [
        "route_after_search_review",
        "route_after_read",
        "route_after_critique",
        "route_after_draft_review",
        "check_token_budget",
    ]:
        assert name in ROUTER_REGISTRY


# ═══════════════════════════════════════════════
#  HITL / feedback node tests
# ═══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_human_review_search():
    result = await human_review_search({})
    assert result["current_phase"] == "search_review"


@pytest.mark.asyncio
async def test_human_review_outline():
    result = await human_review_outline({})
    assert result["current_phase"] == "outline_review"


@pytest.mark.asyncio
async def test_human_review_draft():
    result = await human_review_draft({})
    assert result["current_phase"] == "draft_review"


@pytest.mark.asyncio
async def test_check_read_feedback_with_queries():
    state = {"feedback_search_queries": ["extra"], "feedback_iteration_count": 0}
    result = await check_read_feedback(state)
    assert result["feedback_iteration_count"] == 1


@pytest.mark.asyncio
async def test_check_read_feedback_no_queries():
    state = {"feedback_search_queries": []}
    result = await check_read_feedback(state)
    assert result == {}


@pytest.mark.asyncio
async def test_check_critic_feedback_with_queries():
    state = {"feedback_search_queries": ["gap query"], "feedback_iteration_count": 0}
    result = await check_critic_feedback(state)
    assert result["feedback_iteration_count"] == 1


@pytest.mark.asyncio
async def test_check_critic_feedback_no_queries():
    state = {"feedback_search_queries": []}
    result = await check_critic_feedback(state)
    assert result == {}


# ═══════════════════════════════════════════════
#  Config loading tests
# ═══════════════════════════════════════════════


def test_load_workflow_config():
    config = load_workflow_config()
    assert "workflow" in config
    assert "nodes" in config["workflow"]
    assert "edges" in config["workflow"]

    node_names = [n["name"] for n in config["workflow"]["nodes"]]
    assert "parse_intent" in node_names
    assert "search" in node_names
    assert "export" in node_names


def test_disabled_nodes_in_config():
    config = load_workflow_config()
    disabled = [
        n["name"]
        for n in config["workflow"]["nodes"]
        if not n.get("enabled", True)
    ]
    # v0.3: analyze + critique are now enabled
    assert "analyze" not in disabled
    assert "critique" not in disabled


# ═══════════════════════════════════════════════
#  Graph build tests
# ═══════════════════════════════════════════════


def test_build_review_graph_node_count():
    graph = build_review_graph()
    node_names = list(graph.nodes.keys())
    # v0.3: 15 enabled nodes (analyze + critique + check_critic_feedback added)
    assert len(node_names) == 15
    assert "analyze" in node_names
    assert "critique" in node_names
    assert "check_critic_feedback" in node_names
    assert "revise_review" in node_names


def test_build_review_graph_includes_hitl():
    graph = build_review_graph()
    node_names = list(graph.nodes.keys())
    assert "human_review_search" in node_names
    assert "human_review_outline" in node_names
    assert "human_review_draft" in node_names


def test_build_review_graph_includes_feedback():
    graph = build_review_graph()
    assert "check_read_feedback" in graph.nodes


def test_compile_with_memory_saver():
    compiled = compile_review_graph(checkpointer=MemorySaver())
    assert compiled is not None


# ═══════════════════════════════════════════════
#  Flow execution tests (mock agents)
# ═══════════════════════════════════════════════


def _make_mock_registry():
    """Create a registry with mock agent node functions.

    All nodes return minimal state updates to let the workflow
    flow through without actual LLM calls.
    """
    from app.agents.registry import AgentRegistry

    reg = AgentRegistry()

    async def _parse_intent(state):
        return {
            "search_strategy": {"queries": [{"query": state["user_query"]}]},
            "current_phase": "searching",
        }

    async def _search(state):
        return {
            "candidate_papers": [
                {"title": "Paper A", "s2_id": "s2-1", "authors": ["A"]},
                {"title": "Paper B", "s2_id": "s2-2", "authors": ["B"]},
            ],
            "current_phase": "search_review",
            "feedback_search_queries": [],
        }

    async def _human_review_search(state):
        return {
            "selected_papers": state.get("candidate_papers", []),
            "current_phase": "reading",
        }

    async def _read(state):
        papers = state.get("selected_papers", [])
        return {
            "paper_analyses": [
                {"paper_id": p.get("s2_id", str(i)), "title": p.get("title", ""), "objective": "obj"}
                for i, p in enumerate(papers)
            ],
            "feedback_search_queries": [],
            "current_phase": "outlining",
            "fulltext_coverage": {"total": len(papers), "fulltext_count": 0, "abstract_only_count": len(papers)},
        }

    async def _check_read_feedback(state):
        feedback = state.get("feedback_search_queries", [])
        count = state.get("feedback_iteration_count", 0)
        if feedback:
            return {"feedback_iteration_count": count + 1}
        return {}

    async def _generate_outline(state):
        return {
            "outline": {
                "title": "Test Review",
                "sections": [{"heading": "Intro", "description": "Background", "relevant_paper_indices": []}],
            },
            "current_phase": "outline_review",
        }

    async def _analyze(state):
        return {
            "topic_clusters": [{"id": "c0", "name": "Cluster 0", "paper_ids": [], "paper_count": 0}],
            "comparison_matrix": {"title": "Matrix", "dimensions": [], "methods": [], "narrative": ""},
            "citation_network": {"nodes": [], "edges": [], "key_papers": [], "bridge_papers": []},
            "timeline": [],
            "research_trends": {"by_year": [], "by_topic": [], "emerging_topics": [], "narrative": ""},
            "current_phase": "critiquing",
        }

    async def _critique(state):
        return {
            "quality_assessments": [],
            "contradictions": [],
            "research_gaps": [],
            "limitation_summary": "",
            "feedback_search_queries": [],
            "current_phase": "outlining",
        }

    async def _check_critic_feedback(state):
        feedback = state.get("feedback_search_queries", [])
        count = state.get("feedback_iteration_count", 0)
        if feedback:
            return {"feedback_iteration_count": count + 1}
        return {}

    async def _human_review_outline(state):
        return {"current_phase": "writing"}

    async def _write_review(state):
        return {
            "full_draft": "# Draft\n\nContent...",
            "references": [{"paper_id": "s2-1", "title": "Paper A", "formatted": "A (2024). Paper A."}],
            "current_phase": "verifying",
        }

    async def _verify_citations(state):
        refs = state.get("references", [])
        return {
            "citation_verification": [{"paper_id": r["paper_id"], "status": "verified"} for r in refs],
            "current_phase": "draft_review",
        }

    async def _human_review_draft(state):
        return {"current_phase": "exporting"}

    async def _export(state):
        return {"final_output": state.get("full_draft", ""), "current_phase": "completed"}

    async def _revise_review(state):
        return {"full_draft": "# Revised\n\nBetter content.", "revision_instructions": ""}

    reg.register("parse_intent", _parse_intent)
    reg.register("search", _search)
    reg.register("human_review_search", _human_review_search)
    reg.register("read", _read)
    reg.register("check_read_feedback", _check_read_feedback)
    reg.register("generate_outline", _generate_outline)
    reg.register("analyze", _analyze)
    reg.register("critique", _critique)
    reg.register("check_critic_feedback", _check_critic_feedback)
    reg.register("human_review_outline", _human_review_outline)
    reg.register("write_review", _write_review)
    reg.register("verify_citations", _verify_citations)
    reg.register("human_review_draft", _human_review_draft)
    reg.register("export", _export)
    reg.register("revise_review", _revise_review)

    return reg


@pytest.mark.asyncio
async def test_full_workflow_no_hitl():
    """Run the full workflow with mock agents, all HITL auto-pass (no interrupts)."""
    registry = _make_mock_registry()
    graph = build_review_graph(registry=registry)
    # Compile WITHOUT interrupt_before → no pausing
    compiled = graph.compile()

    initial_state = {
        "user_query": "LLM in code generation",
        "output_language": "zh",
        "citation_style": "apa",
        "output_types": ["full_review"],
    }

    result = await compiled.ainvoke(initial_state)
    assert result["current_phase"] == "completed"
    assert "final_output" in result
    assert len(result.get("candidate_papers", [])) > 0
    assert len(result.get("paper_analyses", [])) > 0


@pytest.mark.asyncio
async def test_workflow_hitl_pause_resume():
    """Workflow should pause at HITL interrupt, then resume with user input."""
    registry = _make_mock_registry()
    graph = build_review_graph(registry=registry)
    checkpointer = MemorySaver()

    compiled = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_review_search", "human_review_outline", "human_review_draft"],
    )

    initial_state = {
        "user_query": "LLM in code generation",
        "output_language": "zh",
        "citation_style": "apa",
        "output_types": ["full_review"],
    }
    thread_config = {"configurable": {"thread_id": "test-project-1"}}

    # Step 1: Run until first HITL (human_review_search)
    result = await compiled.ainvoke(initial_state, config=thread_config)
    assert len(result.get("candidate_papers", [])) > 0

    # Step 2: User selects papers → update state and resume
    await compiled.aupdate_state(
        thread_config,
        {"selected_papers": result["candidate_papers"], "needs_more_search": False},
        as_node="human_review_search",
    )
    result = await compiled.ainvoke(None, config=thread_config)
    # Should have paused before human_review_outline
    assert result.get("outline") is not None

    # Step 3: Approve outline → resume
    await compiled.aupdate_state(thread_config, {}, as_node="human_review_outline")
    result = await compiled.ainvoke(None, config=thread_config)
    # Should have paused before human_review_draft
    assert "full_draft" in result

    # Step 4: Approve draft → resume to completion
    await compiled.aupdate_state(thread_config, {}, as_node="human_review_draft")
    result = await compiled.ainvoke(None, config=thread_config)
    assert result["current_phase"] == "completed"
    assert "final_output" in result


@pytest.mark.asyncio
async def test_workflow_draft_revision_loop():
    """After draft review, user provides revision instructions → revise → re-review."""
    registry = _make_mock_registry()
    graph = build_review_graph(registry=registry)
    checkpointer = MemorySaver()

    compiled = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_review_search", "human_review_outline", "human_review_draft"],
    )

    initial_state = {
        "user_query": "test",
        "output_language": "zh",
        "citation_style": "apa",
        "output_types": ["full_review"],
    }
    cfg = {"configurable": {"thread_id": "test-revision"}}

    # Run to first HITL (human_review_search)
    result = await compiled.ainvoke(initial_state, config=cfg)

    # Pass search review → update state + resume
    await compiled.aupdate_state(
        cfg,
        {"selected_papers": result["candidate_papers"]},
        as_node="human_review_search",
    )
    await compiled.ainvoke(None, config=cfg)

    # Pass outline review
    await compiled.aupdate_state(cfg, {}, as_node="human_review_outline")
    result = await compiled.ainvoke(None, config=cfg)
    # At draft review
    assert "full_draft" in result

    # Request revision → update state with instructions, resume
    await compiled.aupdate_state(
        cfg,
        {"revision_instructions": "Improve the intro"},
        as_node="human_review_draft",
    )
    result = await compiled.ainvoke(None, config=cfg)

    # Should have looped: revise_review → human_review_draft (paused again)
    assert "Revised" in result.get("full_draft", "")

    # Now approve → export
    await compiled.aupdate_state(cfg, {"revision_instructions": ""}, as_node="human_review_draft")
    result = await compiled.ainvoke(None, config=cfg)
    assert result["current_phase"] == "completed"


@pytest.mark.asyncio
async def test_workflow_feedback_loop():
    """Reader feedback triggers supplemental search, up to max iterations."""
    from app.agents.registry import AgentRegistry

    call_count = {"search": 0}

    async def _search(state):
        call_count["search"] += 1
        return {
            "candidate_papers": [{"title": f"Paper {call_count['search']}", "s2_id": f"s2-{call_count['search']}", "authors": ["A"]}],
            "current_phase": "search_review",
            "feedback_search_queries": [],
        }

    async def _read(state):
        # First read triggers feedback; second read doesn't
        iteration = state.get("feedback_iteration_count", 0)
        feedback = ["supplemental query"] if iteration < 1 else []
        return {
            "paper_analyses": [{"paper_id": "p1", "title": "P", "objective": "O"}],
            "feedback_search_queries": feedback,
            "current_phase": "outlining",
        }

    registry = _make_mock_registry()
    registry.register("search", _search)
    registry.register("read", _read)

    graph = build_review_graph(registry=registry)
    compiled = graph.compile()

    initial_state = {
        "user_query": "test",
        "output_language": "zh",
        "citation_style": "apa",
        "output_types": ["full_review"],
    }

    result = await compiled.ainvoke(initial_state)

    # Search should be called twice: initial + one feedback round
    assert call_count["search"] == 2
    assert result["current_phase"] == "completed"
