"""Integration tests for v0.3 workflow — 6-Agent DAG + Critic feedback loop."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from langgraph.checkpoint.memory import MemorySaver

from app.agents.orchestrator import build_review_graph
from app.agents.registry import AgentRegistry


# ── Mock registry for 6-Agent workflow ──


def _make_v03_registry(
    critic_feedback: list[str] | None = None,
) -> AgentRegistry:
    """Create a full 6-Agent mock registry.

    Args:
        critic_feedback: If provided, the critique node will emit these
            as feedback_search_queries on the first call only.
    """
    reg = AgentRegistry()
    critique_call_count = {"n": 0}

    async def _parse_intent(state):
        return {
            "search_strategy": {"queries": [{"query": state["user_query"]}]},
            "current_phase": "searching",
        }

    async def _search(state):
        return {
            "candidate_papers": [
                {"title": "Paper A", "s2_id": "s2-1", "authors": ["A"], "citation_count": 50},
                {"title": "Paper B", "s2_id": "s2-2", "authors": ["B"], "citation_count": 30},
                {"title": "Paper C", "s2_id": "s2-3", "authors": ["C"], "citation_count": 10},
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
                {
                    "paper_id": p.get("s2_id", str(i)),
                    "title": p.get("title", ""),
                    "year": 2020 + i,
                    "objective": f"Objective {i}",
                    "methodology": f"Method {i}",
                    "findings": f"Finding {i}",
                    "limitations": f"Limitation {i}",
                    "method_category": ["supervised", "unsupervised", "reinforcement"][i % 3],
                    "key_concepts": [f"concept_{i}"],
                    "citation_count": p.get("citation_count", 10),
                }
                for i, p in enumerate(papers)
            ],
            "feedback_search_queries": [],
            "current_phase": "analyzing",
            "fulltext_coverage": {
                "total": len(papers),
                "fulltext_count": 0,
                "abstract_only_count": len(papers),
            },
        }

    async def _check_read_feedback(state):
        feedback = state.get("feedback_search_queries", [])
        count = state.get("feedback_iteration_count", 0)
        if feedback:
            return {"feedback_iteration_count": count + 1}
        return {}

    async def _analyze(state):
        analyses = state.get("paper_analyses", [])
        return {
            "topic_clusters": [
                {
                    "id": "cluster_0",
                    "name": "Main Cluster",
                    "paper_ids": [a["paper_id"] for a in analyses],
                    "paper_count": len(analyses),
                    "key_terms": ["term1", "term2"],
                    "summary": "A cluster of papers.",
                }
            ],
            "comparison_matrix": {
                "title": "方法对比矩阵",
                "dimensions": [{"key": "accuracy", "label": "Accuracy", "unit": "%"}],
                "methods": [
                    {"name": "MethodA", "category": "supervised",
                     "paper_id": "s2-1", "values": {"accuracy": 95.0}}
                ],
                "narrative": "MethodA achieves best accuracy.",
            },
            "citation_network": {
                "nodes": [{"id": a["paper_id"], "title": a["title"]} for a in analyses],
                "edges": [],
                "key_papers": [analyses[0]["paper_id"]] if analyses else [],
                "bridge_papers": [],
            },
            "timeline": [{"year": 2020, "milestone": None, "paper_ids": [], "paper_count": 1, "key_event": None}],
            "research_trends": {
                "by_year": [{"year": 2020, "count": 1, "citations_sum": 50}],
                "by_topic": [{"topic": "Main Cluster", "trend": "rising", "yearly_counts": []}],
                "emerging_topics": ["new_topic"],
                "narrative": "Trends are rising.",
            },
            "current_phase": "critiquing",
        }

    async def _critique(state):
        critique_call_count["n"] += 1
        analyses = state.get("paper_analyses", [])

        # On first call, optionally emit feedback queries
        feedback = []
        if critic_feedback and critique_call_count["n"] == 1:
            feedback = critic_feedback

        return {
            "quality_assessments": [
                {"paper_id": a["paper_id"], "quality_score": 0.8, "justification": "Good"}
                for a in analyses
            ],
            "contradictions": [],
            "research_gaps": [
                {"id": "gap_1", "description": "A gap", "priority": "medium",
                 "evidence": [], "related_cluster_ids": [], "suggested_direction": "dir"}
            ],
            "limitation_summary": "Common limitations across papers.",
            "feedback_search_queries": feedback,
            "current_phase": "outlining",
        }

    async def _check_critic_feedback(state):
        feedback = state.get("feedback_search_queries", [])
        count = state.get("feedback_iteration_count", 0)
        if feedback:
            return {"feedback_iteration_count": count + 1}
        return {}

    async def _generate_outline(state):
        return {
            "outline": {
                "title": "Test Review",
                "sections": [
                    {"heading": "Introduction", "description": "Background",
                     "relevant_paper_indices": [0, 1]},
                    {"heading": "Methods", "description": "Methodology comparison",
                     "relevant_paper_indices": [0, 1, 2]},
                ],
            },
            "current_phase": "outline_review",
        }

    async def _human_review_outline(state):
        return {"current_phase": "writing"}

    async def _write_review(state):
        return {
            "full_draft": "# Literature Review\n\nContent with analysis...",
            "references": [
                {"paper_id": "s2-1", "title": "Paper A", "formatted": "A (2024). Paper A."},
            ],
            "current_phase": "verifying",
        }

    async def _verify_citations(state):
        refs = state.get("references", [])
        return {
            "citation_verification": [
                {"paper_id": r["paper_id"], "status": "verified"} for r in refs
            ],
            "current_phase": "review_assessment",
        }

    async def _review_assessment(state):
        return {
            "review_scores": {"coherence": 7, "depth": 7, "rigor": 8, "utility": 7, "weighted": 7.2},
            "review_feedback": [],
            "current_phase": "draft_review",
        }

    async def _auto_revise(state):
        iteration = state.get("revision_iteration_count", 0)
        return {
            "full_draft": "# Auto-revised\n\nImproved.",
            "revision_iteration_count": iteration + 1,
            "revision_contract": {"focus_dimensions": ["depth"], "targets": {"depth": 7}},
            "revision_score_history": [{"iteration": iteration, "scores": state.get("review_scores", {})}],
            "current_phase": "review_assessment",
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
    reg.register("analyze", _analyze)
    reg.register("critique", _critique)
    reg.register("check_critic_feedback", _check_critic_feedback)
    reg.register("generate_outline", _generate_outline)
    reg.register("human_review_outline", _human_review_outline)
    reg.register("write_review", _write_review)
    reg.register("verify_citations", _verify_citations)
    reg.register("review_assessment", _review_assessment)
    reg.register("auto_revise", _auto_revise)
    reg.register("human_review_draft", _human_review_draft)
    reg.register("export", _export)
    reg.register("revise_review", _revise_review)

    return reg


# ═══════════════════════════════════════════════
#  6-Agent DAG flow tests
# ═══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_v03_full_dag_no_hitl():
    """Complete 6-Agent flow: search → read → analyze → critique → write → export."""
    registry = _make_v03_registry()
    graph = build_review_graph(registry=registry)
    compiled = graph.compile()

    initial_state = {
        "user_query": "transformer methods in NLP",
        "output_language": "zh",
        "citation_style": "apa",
        "output_types": ["full_review"],
    }

    result = await compiled.ainvoke(initial_state)

    # Workflow completed
    assert result["current_phase"] == "completed"
    assert "final_output" in result

    # Search phase produced papers
    assert len(result.get("candidate_papers", [])) == 3

    # Reader analyzed papers
    assert len(result.get("paper_analyses", [])) == 3

    # Analyst produced clusters + matrix + network + trends
    assert len(result.get("topic_clusters", [])) >= 1
    assert result["topic_clusters"][0]["name"] == "Main Cluster"
    assert "dimensions" in result.get("comparison_matrix", {})
    assert "nodes" in result.get("citation_network", {})
    assert "by_year" in result.get("research_trends", {})

    # Critic produced assessments + gaps
    assert len(result.get("quality_assessments", [])) == 3
    assert all(0.0 <= a["quality_score"] <= 1.0 for a in result["quality_assessments"])
    assert len(result.get("research_gaps", [])) >= 1
    assert isinstance(result.get("limitation_summary", ""), str)

    # Writer produced draft
    assert "Literature Review" in result.get("full_draft", "")


@pytest.mark.asyncio
async def test_v03_full_dag_with_hitl():
    """6-Agent flow with HITL pauses at search review, outline, and draft."""
    registry = _make_v03_registry()
    graph = build_review_graph(registry=registry)
    checkpointer = MemorySaver()

    compiled = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_review_search", "human_review_outline", "human_review_draft"],
    )

    cfg = {"configurable": {"thread_id": "test-v03-hitl"}}
    initial_state = {
        "user_query": "deep learning NLP",
        "output_language": "en",
        "citation_style": "ieee",
        "output_types": ["full_review"],
    }

    # Step 1: Run to search review
    result = await compiled.ainvoke(initial_state, config=cfg)
    assert len(result.get("candidate_papers", [])) == 3

    # Step 2: User approves papers
    await compiled.aupdate_state(
        cfg,
        {"selected_papers": result["candidate_papers"], "needs_more_search": False},
        as_node="human_review_search",
    )
    result = await compiled.ainvoke(None, config=cfg)
    # Should pause at outline review — analyst + critic already ran
    assert result.get("outline") is not None
    assert len(result.get("topic_clusters", [])) >= 1
    assert len(result.get("quality_assessments", [])) >= 1

    # Step 3: Approve outline
    await compiled.aupdate_state(cfg, {}, as_node="human_review_outline")
    result = await compiled.ainvoke(None, config=cfg)
    # Should pause at draft review
    assert "full_draft" in result

    # Step 4: Approve draft → export
    await compiled.aupdate_state(cfg, {}, as_node="human_review_draft")
    result = await compiled.ainvoke(None, config=cfg)
    assert result["current_phase"] == "completed"


# ═══════════════════════════════════════════════
#  Critic feedback loop tests
# ═══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_v03_critic_feedback_loop():
    """Critic triggers supplementary search, then second pass has no feedback."""
    search_call_count = {"n": 0}

    registry = _make_v03_registry(critic_feedback=["supplementary query"])

    # Override search to track call count
    original_search = registry.get("search")

    async def _counting_search(state):
        search_call_count["n"] += 1
        return await original_search(state)

    registry.register("search", _counting_search)

    graph = build_review_graph(registry=registry)
    compiled = graph.compile()

    initial_state = {
        "user_query": "emerging NLP methods",
        "output_language": "zh",
        "citation_style": "apa",
        "output_types": ["full_review"],
    }

    result = await compiled.ainvoke(initial_state)

    # Search should be called twice: initial + one critic feedback round
    assert search_call_count["n"] == 2
    assert result["current_phase"] == "completed"
    assert "final_output" in result


@pytest.mark.asyncio
async def test_v03_critic_feedback_max_iterations():
    """Critic feedback loop respects max_feedback_iterations = 2."""
    search_call_count = {"n": 0}
    critique_call_count = {"n": 0}

    reg = AgentRegistry()

    async def _parse_intent(state):
        return {"search_strategy": {"queries": []}, "current_phase": "searching"}

    async def _search(state):
        search_call_count["n"] += 1
        return {
            "candidate_papers": [{"title": f"P{search_call_count['n']}", "s2_id": f"s2-{search_call_count['n']}", "authors": []}],
            "feedback_search_queries": [],
            "current_phase": "search_review",
        }

    async def _human_review_search(state):
        return {"selected_papers": state.get("candidate_papers", []), "current_phase": "reading"}

    async def _read(state):
        return {
            "paper_analyses": [{"paper_id": "p1", "title": "P", "objective": "O",
                               "year": 2023, "method_category": "ml", "key_concepts": ["a"],
                               "methodology": "M", "findings": "F", "limitations": "L",
                               "citation_count": 10}],
            "feedback_search_queries": [],
            "current_phase": "analyzing",
        }

    async def _check_read_feedback(state):
        feedback = state.get("feedback_search_queries", [])
        count = state.get("feedback_iteration_count", 0)
        if feedback:
            return {"feedback_iteration_count": count + 1}
        return {}

    async def _analyze(state):
        return {
            "topic_clusters": [{"id": "c0", "name": "C", "paper_ids": ["p1"], "paper_count": 1, "key_terms": []}],
            "comparison_matrix": {"title": "M", "dimensions": [], "methods": [], "narrative": ""},
            "citation_network": {"nodes": [], "edges": [], "key_papers": [], "bridge_papers": []},
            "timeline": [],
            "research_trends": {"by_year": [], "by_topic": [], "emerging_topics": [], "narrative": ""},
            "current_phase": "critiquing",
        }

    async def _critique(state):
        critique_call_count["n"] += 1
        # Always request more search — should be limited by max_feedback_iterations
        return {
            "quality_assessments": [],
            "contradictions": [],
            "research_gaps": [],
            "limitation_summary": "",
            "feedback_search_queries": ["always need more"],
            "current_phase": "outlining",
        }

    async def _check_critic_feedback(state):
        feedback = state.get("feedback_search_queries", [])
        count = state.get("feedback_iteration_count", 0)
        if feedback:
            return {"feedback_iteration_count": count + 1}
        return {}

    async def _generate_outline(state):
        return {"outline": {"title": "T", "sections": []}, "current_phase": "outline_review"}

    async def _human_review_outline(state):
        return {"current_phase": "writing"}

    async def _write_review(state):
        return {"full_draft": "Draft", "references": [], "current_phase": "verifying"}

    async def _verify_citations(state):
        return {"citation_verification": [], "current_phase": "review_assessment"}

    async def _review_assessment(state):
        return {
            "review_scores": {"coherence": 7, "depth": 7, "rigor": 8, "utility": 7, "weighted": 7.2},
            "review_feedback": [],
            "current_phase": "draft_review",
        }

    async def _auto_revise(state):
        iteration = state.get("revision_iteration_count", 0)
        return {
            "full_draft": "Auto-revised",
            "revision_iteration_count": iteration + 1,
            "current_phase": "review_assessment",
        }

    async def _human_review_draft(state):
        return {"current_phase": "exporting"}

    async def _export(state):
        return {"final_output": state.get("full_draft", ""), "current_phase": "completed"}

    async def _revise_review(state):
        return {"full_draft": "Revised", "revision_instructions": ""}

    reg.register("parse_intent", _parse_intent)
    reg.register("search", _search)
    reg.register("human_review_search", _human_review_search)
    reg.register("read", _read)
    reg.register("check_read_feedback", _check_read_feedback)
    reg.register("analyze", _analyze)
    reg.register("critique", _critique)
    reg.register("check_critic_feedback", _check_critic_feedback)
    reg.register("generate_outline", _generate_outline)
    reg.register("human_review_outline", _human_review_outline)
    reg.register("write_review", _write_review)
    reg.register("verify_citations", _verify_citations)
    reg.register("review_assessment", _review_assessment)
    reg.register("auto_revise", _auto_revise)
    reg.register("human_review_draft", _human_review_draft)
    reg.register("export", _export)
    reg.register("revise_review", _revise_review)

    graph = build_review_graph(registry=reg)
    compiled = graph.compile()

    result = await compiled.ainvoke({
        "user_query": "test",
        "output_language": "zh",
        "citation_style": "apa",
        "output_types": ["full_review"],
    })

    # search_call_count: 1 initial + 1 feedback loop (2nd feedback capped at MAX) = 2
    assert search_call_count["n"] == 2
    # critique ran 2 times: once initially, once after feedback loop
    assert critique_call_count["n"] == 2
    assert result["current_phase"] == "completed"


@pytest.mark.asyncio
async def test_v03_analyst_output_passes_to_critic():
    """Verify Analyst output (clusters, trends) is available to Critic."""
    received_state = {}

    registry = _make_v03_registry()

    # Override critique to capture state
    async def _capturing_critique(state):
        received_state.update({
            "topic_clusters": state.get("topic_clusters"),
            "research_trends": state.get("research_trends"),
            "comparison_matrix": state.get("comparison_matrix"),
        })
        return {
            "quality_assessments": [],
            "contradictions": [],
            "research_gaps": [],
            "limitation_summary": "",
            "feedback_search_queries": [],
            "current_phase": "outlining",
        }

    registry.register("critique", _capturing_critique)

    graph = build_review_graph(registry=registry)
    compiled = graph.compile()

    await compiled.ainvoke({
        "user_query": "test",
        "output_language": "zh",
        "citation_style": "apa",
        "output_types": ["full_review"],
    })

    # Critic should have received Analyst output
    assert received_state["topic_clusters"] is not None
    assert len(received_state["topic_clusters"]) >= 1
    assert received_state["research_trends"] is not None
    assert "by_year" in received_state["research_trends"]
    assert received_state["comparison_matrix"] is not None


@pytest.mark.asyncio
async def test_v03_node_order_in_graph():
    """Verify the correct node ordering in the compiled graph."""
    graph = build_review_graph()
    node_names = list(graph.nodes.keys())

    # All 17 nodes should be present (15 original + review_assessment + auto_revise)
    expected = [
        "parse_intent", "search", "human_review_search",
        "read", "check_read_feedback",
        "analyze", "critique", "check_critic_feedback",
        "generate_outline", "human_review_outline",
        "write_review", "verify_citations",
        "review_assessment", "auto_revise",
        "human_review_draft",
        "revise_review", "export",
    ]
    for name in expected:
        assert name in node_names, f"{name} missing from graph"
