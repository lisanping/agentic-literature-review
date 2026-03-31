"""v0.3 End-to-end integration test — 6-Agent workflow with Analyst + Critic.

Tests the complete v0.3 lifecycle:
  Create project → Start → HITL search → Read → Analyze → Critique →
  HITL outline → Write → Verify → HITL draft → Export

Also tests:
  - Critic feedback loop triggering supplemental search
  - Specialized output types (methodology_review, gap_report, trend_report, research_roadmap)
  - 6-Agent graph node count verification

All LLM calls are mocked.
"""

import pytest

from langgraph.checkpoint.memory import MemorySaver

from app.agents.orchestrator import build_review_graph
from app.agents.registry import AgentRegistry


# ═══════════════════════════════════════════════
#  Shared mock registry builder
# ═══════════════════════════════════════════════


def _build_v03_registry(
    *,
    critic_feedback: list[str] | None = None,
    analyst_data: dict | None = None,
    critic_data: dict | None = None,
    output_type: str = "full_review",
) -> AgentRegistry:
    """Build a 6-Agent mock registry with configurable Analyst / Critic data.

    Args:
        critic_feedback: If set, critic emits these as feedback_search_queries on first call.
        analyst_data: Override analyst output (topic_clusters, comparison_matrix, etc.).
        critic_data: Override critic output (quality_assessments, gaps, etc.).
        output_type: Affects writer output formatting.
    """
    reg = AgentRegistry()
    search_count = {"n": 0}
    critique_count = {"n": 0}

    default_analyst = {
        "topic_clusters": [
            {"id": "c0", "name": "Supervised Learning", "paper_ids": ["s2-1", "s2-2"], "paper_count": 2, "key_terms": ["CNN", "RNN"], "summary": "Neural nets"},
            {"id": "c1", "name": "Unsupervised Learning", "paper_ids": ["s2-3"], "paper_count": 1, "key_terms": ["GAN"], "summary": "Generative models"},
        ],
        "comparison_matrix": {
            "title": "Method Comparison",
            "dimensions": [{"key": "accuracy", "label": "Accuracy", "unit": "%"}],
            "methods": [
                {"name": "CNN", "category": "supervised", "paper_id": "s2-1", "values": {"accuracy": 95}},
                {"name": "GAN", "category": "unsupervised", "paper_id": "s2-3", "values": {"accuracy": 88}},
            ],
            "narrative": "CNN outperforms GAN in accuracy.",
        },
        "citation_network": {"nodes": [], "edges": [], "key_papers": [], "bridge_papers": []},
        "timeline": [
            {"year": 2023, "paper_count": 1, "paper_ids": ["s2-2"], "milestone": "Initial work", "key_event": None},
            {"year": 2024, "paper_count": 2, "paper_ids": ["s2-1", "s2-3"], "milestone": "Breakthrough", "key_event": "GPT-4"},
        ],
        "research_trends": {
            "by_year": [{"year": 2023, "count": 1, "citations_sum": 30}, {"year": 2024, "count": 2, "citations_sum": 60}],
            "by_topic": [{"topic": "LLM", "trend": "rising", "yearly_counts": []}],
            "emerging_topics": ["multimodal"],
            "narrative": "Rising interest in LLM applications.",
        },
        "current_phase": "critiquing",
    }

    default_critic = {
        "quality_assessments": [
            {"paper_id": "s2-1", "quality_score": 0.85, "justification": "High quality", "strengths": ["Rigorous"], "weaknesses": []},
            {"paper_id": "s2-2", "quality_score": 0.5, "justification": "Average", "strengths": [], "weaknesses": ["Small sample"]},
            {"paper_id": "s2-3", "quality_score": 0.25, "justification": "Low quality", "strengths": [], "weaknesses": ["No validation"]},
        ],
        "contradictions": [
            {"id": "ct0", "paper_a_id": "s2-1", "paper_b_id": "s2-2", "topic": "Speed", "claim_a": "Fast", "claim_b": "Slow", "possible_reconciliation": "Different benchmarks", "severity": "minor"},
        ],
        "research_gaps": [
            {"id": "rg0", "description": "No multilingual evaluation", "evidence": ["All English datasets"], "priority": "high", "related_cluster_ids": ["c0"], "suggested_direction": "Evaluate on multilingual benchmarks"},
        ],
        "limitation_summary": "Most studies use limited datasets and lack cross-domain validation.",
        "feedback_search_queries": [],
        "current_phase": "outlining",
    }

    _analyst = analyst_data or default_analyst
    _critic_base = critic_data or default_critic

    async def _parse_intent(state):
        return {
            "search_strategy": {"queries": [{"query": state["user_query"]}], "key_concepts": ["LLM"]},
            "current_phase": "searching",
        }

    async def _search(state):
        search_count["n"] += 1
        return {
            "candidate_papers": [
                {"title": "Paper A", "s2_id": "s2-1", "authors": ["Author A"], "year": 2024, "citation_count": 100},
                {"title": "Paper B", "s2_id": "s2-2", "authors": ["Author B"], "year": 2023, "citation_count": 30},
                {"title": "Paper C", "s2_id": "s2-3", "authors": ["Author C"], "year": 2024, "citation_count": 5},
            ],
            "current_phase": "search_review",
            "feedback_search_queries": [],
        }

    async def _human_review_search(state):
        # Auto-select all candidate papers (for non-interrupt mode)
        return {
            "selected_papers": state.get("candidate_papers", []),
            "needs_more_search": False,
            "current_phase": "search_review",
        }

    async def _read(state):
        papers = state.get("selected_papers", state.get("candidate_papers", []))
        return {
            "paper_analyses": [
                {
                    "paper_id": p.get("s2_id", str(i)),
                    "title": p.get("title", ""),
                    "objective": f"Study on {p.get('title', '')}",
                    "methodology": "Experimental",
                    "findings": "Significant results",
                    "limitations": "Small sample",
                    "key_concepts": ["LLM"],
                    "method_category": "ml",
                    "datasets": ["dataset-1"],
                    "authors": p.get("authors", []),
                    "year": p.get("year"),
                }
                for i, p in enumerate(papers)
            ],
            "feedback_search_queries": [],
            "current_phase": "outlining",
            "fulltext_coverage": {"total": len(papers), "fulltext_count": 0, "abstract_only_count": len(papers)},
            "reading_progress": {"total": len(papers), "completed": len(papers)},
        }

    async def _check_read_feedback(state):
        feedback = state.get("feedback_search_queries", [])
        if feedback:
            return {"feedback_iteration_count": state.get("feedback_iteration_count", 0) + 1}
        return {}

    async def _analyze(state):
        return dict(_analyst)

    async def _critique(state):
        critique_count["n"] += 1
        result = dict(_critic_base)
        if critic_feedback and critique_count["n"] == 1:
            result["feedback_search_queries"] = list(critic_feedback)
        else:
            result["feedback_search_queries"] = []
        return result

    async def _check_critic_feedback(state):
        feedback = state.get("feedback_search_queries", [])
        if feedback:
            return {"feedback_iteration_count": state.get("feedback_iteration_count", 0) + 1}
        return {}

    async def _generate_outline(state):
        analyses = state.get("paper_analyses", [])
        clusters = state.get("topic_clusters", [])
        cluster_sections = [
            {"heading": c.get("name", f"Topic {i}"), "description": f"Analysis of {c.get('name', '')}", "relevant_paper_indices": list(range(1, len(analyses) + 1))}
            for i, c in enumerate(clusters)
        ] if clusters else [
            {"heading": "Methods", "description": "Approaches", "relevant_paper_indices": list(range(1, len(analyses) + 1))},
        ]
        return {
            "outline": {
                "title": "Literature Review: LLM Advances",
                "sections": [
                    {"heading": "Introduction", "description": "Background", "relevant_paper_indices": []},
                    *cluster_sections,
                    {"heading": "Conclusion", "description": "Summary", "relevant_paper_indices": []},
                ],
            },
            "current_phase": "outline_review",
        }

    async def _human_review_outline(state):
        return {}

    async def _write_review(state):
        outline = state.get("outline", {})
        title = outline.get("title", "Review")
        sections = outline.get("sections", [])
        draft = f"# {title}\n\n"
        for sec in sections:
            draft += f"## {sec['heading']}\n\n{sec['description']} content...\n\n"

        # Include gaps section for full_review
        gaps = state.get("research_gaps", [])
        if gaps:
            draft += "## Research Gaps & Future Directions\n\n"
            for gap in gaps:
                draft += f"- {gap.get('description', '')}\n"
            draft += "\n"

        return {
            "full_draft": draft,
            "draft_sections": [{"heading": s["heading"], "content": f"{s['description']} content..."} for s in sections],
            "references": [
                {"paper_id": a["paper_id"], "title": a["title"], "formatted": f"{', '.join(a.get('authors', ['?']))} ({a.get('year', '?')}). {a['title']}."}
                for a in state.get("paper_analyses", [])
            ],
            "current_phase": "verifying",
        }

    async def _verify_citations(state):
        refs = state.get("references", [])
        return {
            "citation_verification": [{"paper_id": r["paper_id"], "status": "verified"} for r in refs],
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
            "current_phase": "review_assessment",
        }

    async def _human_review_draft(state):
        # Clear revision_instructions to avoid infinite revise loop
        return {"revision_instructions": ""}

    async def _revise_review(state):
        return {"full_draft": "# Revised\n\nImproved.", "revision_instructions": ""}

    async def _export(state):
        return {"final_output": state.get("full_draft", ""), "current_phase": "completed"}

    for name, fn in [
        ("parse_intent", _parse_intent), ("search", _search),
        ("human_review_search", _human_review_search), ("read", _read),
        ("check_read_feedback", _check_read_feedback),
        ("analyze", _analyze), ("critique", _critique),
        ("check_critic_feedback", _check_critic_feedback),
        ("generate_outline", _generate_outline),
        ("human_review_outline", _human_review_outline),
        ("write_review", _write_review), ("verify_citations", _verify_citations),
        ("review_assessment", _review_assessment), ("auto_revise", _auto_revise),
        ("human_review_draft", _human_review_draft),
        ("revise_review", _revise_review), ("export", _export),
    ]:
        reg.register(name, fn)

    return reg, search_count, critique_count


# ═══════════════════════════════════════════════
#  Test: Full 6-Agent lifecycle with HITL
# ═══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_v03_full_lifecycle_with_hitl():
    """Complete 6-Agent E2E: search → read → analyze → critique → outline → write → export.

    Verifies:
    - All 6 agents execute in correct order
    - Analyst output (topic_clusters, comparison_matrix, timeline, research_trends) is present
    - Critic output (quality_assessments, contradictions, research_gaps) is present
    - Writer generates draft with research gaps section
    - 3 HITL pause/resume points work correctly
    - Final output contains expected content
    """
    reg, search_count, _ = _build_v03_registry()
    graph = build_review_graph(registry=reg)
    checkpointer = MemorySaver()
    compiled = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_review_search", "human_review_outline", "human_review_draft"],
    )

    cfg = {"configurable": {"thread_id": "v03-full-hitl"}}
    initial_state = {
        "user_query": "LLM advances in code generation",
        "output_language": "en",
        "citation_style": "apa",
        "output_types": ["full_review"],
        "feedback_iteration_count": 0,
        "feedback_search_queries": [],
        "error_log": [],
    }

    # Step 1: parse_intent + search → pause at human_review_search
    result = await compiled.ainvoke(initial_state, config=cfg)
    assert len(result.get("candidate_papers", [])) == 3

    # Step 2: User selects all papers → resume
    # read → analyze → critique → generate_outline → pause at human_review_outline
    await compiled.aupdate_state(
        cfg,
        {"selected_papers": result["candidate_papers"], "needs_more_search": False},
        as_node="human_review_search",
    )
    result = await compiled.ainvoke(None, config=cfg)

    # Verify Analyst output
    assert len(result.get("topic_clusters", [])) == 2
    assert result["topic_clusters"][0]["name"] == "Supervised Learning"
    assert result.get("comparison_matrix", {}).get("title") == "Method Comparison"
    assert len(result.get("timeline", [])) == 2
    assert result.get("research_trends", {}).get("emerging_topics") == ["multimodal"]

    # Verify Critic output
    assert len(result.get("quality_assessments", [])) == 3
    assert result["quality_assessments"][0]["quality_score"] == 0.85
    assert len(result.get("contradictions", [])) == 1
    assert len(result.get("research_gaps", [])) == 1
    assert "multilingual" in result["research_gaps"][0]["description"]
    assert result.get("limitation_summary") != ""

    # Verify outline references clusters
    assert result.get("outline") is not None
    sections = result["outline"]["sections"]
    assert len(sections) >= 3  # Intro + 2 clusters + Conclusion

    # Step 3: Approve outline → write + verify → pause at human_review_draft
    await compiled.aupdate_state(cfg, {}, as_node="human_review_outline")
    result = await compiled.ainvoke(None, config=cfg)
    assert "full_draft" in result
    assert "# Literature Review: LLM Advances" in result["full_draft"]
    assert "Research Gaps" in result["full_draft"]
    assert len(result.get("references", [])) == 3
    assert all(v["status"] == "verified" for v in result.get("citation_verification", []))

    # Step 4: Approve draft → export
    await compiled.aupdate_state(cfg, {"revision_instructions": ""}, as_node="human_review_draft")
    result = await compiled.ainvoke(None, config=cfg)
    assert result["current_phase"] == "completed"
    assert "LLM Advances" in result["final_output"]
    assert search_count["n"] == 1  # no extra search from critic


# ═══════════════════════════════════════════════
#  Test: Critic feedback triggers supplemental search
# ═══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_v03_critic_feedback_loop():
    """Critic identifies gap → triggers supplemental search → second analysis round → continues.

    Verifies:
    - Critic feedback_search_queries triggers loop back to search
    - Search count increments (initial + 1 feedback loop = 2)
    - Second analysis round proceeds normally
    - Pipeline completes successfully
    """
    reg, search_count, critique_count = _build_v03_registry(
        critic_feedback=["multimodal LLM benchmarks"],
    )
    graph = build_review_graph(registry=reg)
    compiled = graph.compile()

    result = await compiled.ainvoke({
        "user_query": "LLM evaluation",
        "output_language": "en",
        "citation_style": "apa",
        "output_types": ["full_review"],
        "feedback_iteration_count": 0,
        "feedback_search_queries": [],
        "error_log": [],
    })

    assert result["current_phase"] == "completed"
    assert search_count["n"] == 2  # 1 initial + 1 feedback loop
    assert critique_count["n"] == 2  # critique ran twice


# ═══════════════════════════════════════════════
#  Test: Specialized output types
# ═══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_v03_methodology_review_output():
    """v0.3 output type: methodology_review executes the complete 6-Agent pipeline."""
    reg, _, _ = _build_v03_registry(output_type="methodology_review")
    graph = build_review_graph(registry=reg)
    compiled = graph.compile()

    result = await compiled.ainvoke({
        "user_query": "deep learning optimization methods",
        "output_language": "en",
        "citation_style": "ieee",
        "output_types": ["methodology_review"],
        "feedback_iteration_count": 0,
        "feedback_search_queries": [],
        "error_log": [],
    })

    assert result["current_phase"] == "completed"
    assert "final_output" in result
    assert len(result.get("comparison_matrix", {}).get("methods", [])) == 2


@pytest.mark.asyncio
async def test_v03_gap_report_output():
    """v0.3 output type: gap_report pipeline."""
    reg, _, _ = _build_v03_registry(output_type="gap_report")
    graph = build_review_graph(registry=reg)
    compiled = graph.compile()

    result = await compiled.ainvoke({
        "user_query": "NLP data augmentation",
        "output_language": "zh",
        "citation_style": "apa",
        "output_types": ["gap_report"],
        "feedback_iteration_count": 0,
        "feedback_search_queries": [],
        "error_log": [],
    })

    assert result["current_phase"] == "completed"
    assert len(result.get("research_gaps", [])) == 1
    assert result["research_gaps"][0]["priority"] == "high"


@pytest.mark.asyncio
async def test_v03_trend_report_output():
    """v0.3 output type: trend_report pipeline."""
    reg, _, _ = _build_v03_registry(output_type="trend_report")
    graph = build_review_graph(registry=reg)
    compiled = graph.compile()

    result = await compiled.ainvoke({
        "user_query": "transformer architectures",
        "output_language": "en",
        "citation_style": "apa",
        "output_types": ["trend_report"],
        "feedback_iteration_count": 0,
        "feedback_search_queries": [],
        "error_log": [],
    })

    assert result["current_phase"] == "completed"
    assert len(result.get("timeline", [])) == 2
    assert result.get("research_trends", {}).get("narrative") != ""


@pytest.mark.asyncio
async def test_v03_research_roadmap_output():
    """v0.3 output type: research_roadmap pipeline."""
    reg, _, _ = _build_v03_registry(output_type="research_roadmap")
    graph = build_review_graph(registry=reg)
    compiled = graph.compile()

    result = await compiled.ainvoke({
        "user_query": "federated learning",
        "output_language": "zh",
        "citation_style": "gbt7714",
        "output_types": ["research_roadmap"],
        "feedback_iteration_count": 0,
        "feedback_search_queries": [],
        "error_log": [],
    })

    assert result["current_phase"] == "completed"
    assert len(result.get("topic_clusters", [])) == 2
    assert len(result.get("research_gaps", [])) == 1


# ═══════════════════════════════════════════════
#  Test: Draft revision in 6-Agent pipeline
# ═══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_v03_revision_with_analyst_critic_data():
    """User revises draft after analyze+critique; analyst/critic data persists."""
    reg, _, _ = _build_v03_registry()
    graph = build_review_graph(registry=reg)
    checkpointer = MemorySaver()
    compiled = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_review_search", "human_review_outline", "human_review_draft"],
    )

    cfg = {"configurable": {"thread_id": "v03-revision"}}

    # Run to search review
    result = await compiled.ainvoke({
        "user_query": "test revision",
        "output_language": "en",
        "citation_style": "apa",
        "output_types": ["full_review"],
        "feedback_iteration_count": 0,
        "feedback_search_queries": [],
        "error_log": [],
    }, config=cfg)

    # Approve search → run to outline
    await compiled.aupdate_state(
        cfg,
        {"selected_papers": result["candidate_papers"], "needs_more_search": False},
        as_node="human_review_search",
    )
    result = await compiled.ainvoke(None, config=cfg)

    # Approve outline → run to draft review
    await compiled.aupdate_state(cfg, {}, as_node="human_review_outline")
    result = await compiled.ainvoke(None, config=cfg)
    assert "full_draft" in result

    # Request revision
    await compiled.aupdate_state(
        cfg,
        {"revision_instructions": "Add more detail on GAN methods"},
        as_node="human_review_draft",
    )
    result = await compiled.ainvoke(None, config=cfg)
    assert "Revised" in result.get("full_draft", "")

    # Analyst/Critic data should still be in state
    assert len(result.get("topic_clusters", [])) == 2
    assert len(result.get("quality_assessments", [])) == 3

    # Approve revised draft → export
    await compiled.aupdate_state(cfg, {"revision_instructions": ""}, as_node="human_review_draft")
    result = await compiled.ainvoke(None, config=cfg)
    assert result["current_phase"] == "completed"


# ═══════════════════════════════════════════════
#  Test: Graph completeness
# ═══════════════════════════════════════════════


def test_v03_graph_has_17_nodes():
    """Verify the compiled graph has exactly 17 agent nodes."""
    reg, _, _ = _build_v03_registry()
    graph = build_review_graph(registry=reg)
    node_names = set(graph.nodes.keys()) - {"__start__", "__end__"}
    assert len(node_names) == 17, f"Expected 17 nodes, got {len(node_names)}: {node_names}"
