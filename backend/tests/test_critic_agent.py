"""Tests for Critic Agent — quality scoring, contradiction detection, gap analysis."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.critic_agent import (
    _parse_json_response,
    _get_paper_id,
    _persist_quality_scores,
    compute_quality_score,
    build_cluster_paper_pairs,
    generate_feedback_queries,
    assess_review,
    critique_node,
    review_assessment_node,
    RUBRIC_WEIGHTS,
    RUBRIC_DIMENSIONS,
)


# ── Test fixtures ──


def _make_paper(
    paper_id: str,
    title: str = "Paper",
    year: int = 2023,
    method_category: str | None = None,
    methodology: str | None = None,
    findings: str | None = None,
    limitations: str | None = None,
    citation_count: int = 10,
    datasets: list[str] | None = None,
    key_concepts: list[str] | None = None,
) -> dict:
    return {
        "paper_id": paper_id,
        "title": title,
        "year": year,
        "method_category": method_category,
        "methodology": methodology,
        "findings": findings,
        "limitations": limitations,
        "citation_count": citation_count,
        "datasets": datasets or [],
        "key_concepts": key_concepts or [],
    }


def _sample_analyses(n: int = 8) -> list[dict]:
    categories = ["supervised", "unsupervised", "reinforcement"]
    return [
        _make_paper(
            paper_id=f"s2-{i}",
            title=f"Paper {i}",
            year=2020 + (i % 4),
            method_category=categories[i % len(categories)],
            methodology=f"Method {i}",
            findings=f"Finding {i}",
            limitations=f"Limitation {i}",
            citation_count=10 * (i + 1),
        )
        for i in range(n)
    ]


def _sample_clusters(analyses: list[dict]) -> list[dict]:
    """Build simple clusters from analyses."""
    return [
        {
            "id": "cluster_0",
            "name": "Supervised Methods",
            "paper_ids": [_get_paper_id(a) for a in analyses if a.get("method_category") == "supervised"],
            "paper_count": sum(1 for a in analyses if a.get("method_category") == "supervised"),
            "key_terms": ["supervised", "classification"],
        },
        {
            "id": "cluster_1",
            "name": "Unsupervised Methods",
            "paper_ids": [_get_paper_id(a) for a in analyses if a.get("method_category") == "unsupervised"],
            "paper_count": sum(1 for a in analyses if a.get("method_category") == "unsupervised"),
            "key_terms": ["unsupervised", "clustering"],
        },
    ]


def _sample_trends() -> dict:
    return {
        "by_year": [
            {"year": 2020, "count": 2, "citations_sum": 30},
            {"year": 2022, "count": 3, "citations_sum": 50},
        ],
        "by_topic": [
            {"topic": "Supervised Methods", "trend": "stable",
             "yearly_counts": [{"year": 2020, "count": 1}, {"year": 2022, "count": 2}]},
            {"topic": "Rising Topic", "trend": "rising",
             "yearly_counts": [{"year": 2020, "count": 1}]},  # no recent → time gap
        ],
        "emerging_topics": ["new_topic"],
        "narrative": "",
    }


# ── _parse_json_response ──


def test_parse_json_clean():
    text = '{"assessments": [{"paper_id": "p1", "rigor_score": 8}]}'
    result = _parse_json_response(text)
    assert result["assessments"][0]["rigor_score"] == 8


def test_parse_json_markdown_fenced():
    text = '```json\n{"contradictions": []}\n```'
    result = _parse_json_response(text)
    assert result["contradictions"] == []


def test_parse_json_invalid():
    result = _parse_json_response("not valid json")
    assert result is None


# ── _get_paper_id ──


def test_get_paper_id_from_paper_id():
    assert _get_paper_id({"paper_id": "p1"}) == "p1"


def test_get_paper_id_from_s2_id():
    assert _get_paper_id({"s2_id": "s2-123"}) == "s2-123"


def test_get_paper_id_fallback_title():
    assert _get_paper_id({"title": "A Long Paper Title"}) == "A Long Paper Title"


# ── compute_quality_score ──


def test_compute_quality_score_perfect():
    score = compute_quality_score(
        llm_rigor_score=10, citation_count=100, max_citations=100, venue_tier=1.0
    )
    assert score == 1.0


def test_compute_quality_score_zero():
    score = compute_quality_score(
        llm_rigor_score=0, citation_count=0, max_citations=100, venue_tier=0.0
    )
    assert score == 0.0


def test_compute_quality_score_formula():
    # 0.6 * (7/10) + 0.3 * (50/100) + 0.1 * 0.5 = 0.42 + 0.15 + 0.05 = 0.62
    score = compute_quality_score(
        llm_rigor_score=7, citation_count=50, max_citations=100, venue_tier=0.5
    )
    assert score == 0.62


def test_compute_quality_score_zero_max_citations():
    score = compute_quality_score(
        llm_rigor_score=8, citation_count=50, max_citations=0, venue_tier=0.2
    )
    # 0.6 * 0.8 + 0.3 * 0 + 0.1 * 0.2 = 0.48 + 0 + 0.02 = 0.50
    assert score == 0.5


def test_compute_quality_score_clamped():
    score = compute_quality_score(
        llm_rigor_score=15, citation_count=200, max_citations=100, venue_tier=2.0
    )
    assert score <= 1.0


# ── build_cluster_paper_pairs ──


def test_build_cluster_paper_pairs_basic():
    analyses = _sample_analyses(6)
    clusters = _sample_clusters(analyses)

    pairs = build_cluster_paper_pairs(analyses, clusters)
    assert len(pairs) > 0
    for cluster_name, pa, pb in pairs:
        assert isinstance(cluster_name, str)
        assert pa["paper_id"] != pb["paper_id"]


def test_build_cluster_paper_pairs_single_paper_cluster():
    analyses = [_make_paper("p1")]
    clusters = [{"id": "c0", "name": "Solo", "paper_ids": ["p1"], "paper_count": 1}]

    pairs = build_cluster_paper_pairs(analyses, clusters)
    assert pairs == []  # need >= 2 papers for pairs


def test_build_cluster_paper_pairs_limit():
    # Create a large cluster to test MAX_PAIRS_PER_CLUSTER limit
    analyses = [_make_paper(f"p{i}", method_category="same") for i in range(10)]
    clusters = [{
        "id": "c0", "name": "Large",
        "paper_ids": [f"p{i}" for i in range(10)],
        "paper_count": 10,
    }]

    pairs = build_cluster_paper_pairs(analyses, clusters)
    assert len(pairs) <= 10  # MAX_PAIRS_PER_CLUSTER


def test_build_cluster_paper_pairs_empty():
    pairs = build_cluster_paper_pairs([], [])
    assert pairs == []


# ── generate_feedback_queries ──


def test_generate_feedback_queries_coverage_gap():
    clusters = [
        {"name": "Small Topic", "paper_count": 2, "key_terms": ["term1", "term2"]},
        {"name": "Big Topic", "paper_count": 10, "key_terms": ["term3"]},
    ]
    queries = generate_feedback_queries(clusters, [], {"by_topic": []})
    assert len(queries) >= 1
    assert any("term1" in q for q in queries)


def test_generate_feedback_queries_gap_search():
    gaps = [
        {"search_query": "low-resource NLP evaluation", "priority": "high"},
        {"search_query": None, "priority": "medium"},
    ]
    queries = generate_feedback_queries([], gaps, {"by_topic": []})
    assert "low-resource NLP evaluation" in queries


def test_generate_feedback_queries_dedup():
    clusters = [
        {"name": "Topic A", "paper_count": 1, "key_terms": ["term"]},
    ]
    gaps = [{"search_query": "term"}]
    queries = generate_feedback_queries(clusters, gaps, {"by_topic": []})
    assert queries.count("term") == 1  # deduplicated


def test_generate_feedback_queries_empty():
    queries = generate_feedback_queries(
        [{"name": "OK", "paper_count": 5, "key_terms": []}],
        [],
        {"by_topic": []},
    )
    assert queries == []


# ── assess_quality_batch (LLM) ──


@pytest.mark.asyncio
async def test_assess_quality_batch():
    from app.agents.critic_agent import assess_quality_batch

    mock_llm = MagicMock()
    mock_llm.call = AsyncMock(return_value=(
        json.dumps({
            "assessments": [
                {"paper_id": "p1", "rigor_score": 8,
                 "justification": "Well designed", "strengths": ["good data"],
                 "weaknesses": ["small sample"]},
                {"paper_id": "p2", "rigor_score": 5,
                 "justification": "Average", "strengths": [],
                 "weaknesses": ["weak analysis"]},
            ]
        }),
        {"total_input": 100, "total_output": 50, "by_agent": {}},
    ))
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    papers = [
        _make_paper("p1", citation_count=80),
        _make_paper("p2", citation_count=20),
    ]
    assessments, usage = await assess_quality_batch(
        papers, "test query", max_citations=100,
        llm=mock_llm, prompt_manager=mock_pm,
    )

    assert len(assessments) == 2
    assert assessments[0]["paper_id"] == "p1"
    assert 0.0 <= assessments[0]["quality_score"] <= 1.0
    assert assessments[0]["justification"] == "Well designed"
    assert assessments[1]["paper_id"] == "p2"


@pytest.mark.asyncio
async def test_assess_all_papers():
    from app.agents.critic_agent import assess_all_papers

    mock_llm = MagicMock()
    mock_llm.call = AsyncMock(return_value=(
        json.dumps({
            "assessments": [
                {"paper_id": f"s2-{i}", "rigor_score": 7,
                 "justification": "OK", "strengths": [], "weaknesses": []}
                for i in range(8)
            ]
        }),
        {"total_input": 100, "total_output": 50, "by_agent": {}},
    ))
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    analyses = _sample_analyses(8)
    assessments, usage = await assess_all_papers(
        analyses, "query", mock_llm, mock_pm
    )

    assert len(assessments) == 8
    assert all(0.0 <= a["quality_score"] <= 1.0 for a in assessments)


# ── detect_contradictions (LLM) ──


@pytest.mark.asyncio
async def test_detect_contradictions():
    from app.agents.critic_agent import detect_contradictions

    mock_llm = MagicMock()
    mock_llm.call = AsyncMock(return_value=(
        json.dumps({
            "contradictions": [
                {
                    "paper_a_id": "s2-0",
                    "paper_b_id": "s2-3",
                    "topic": "Efficiency",
                    "claim_a": "Method A is faster",
                    "claim_b": "Method A is slower",
                    "possible_reconciliation": "Different datasets used",
                    "severity": "moderate",
                }
            ]
        }),
        {"total_input": 100, "total_output": 50, "by_agent": {}},
    ))
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    analyses = _sample_analyses(6)
    clusters = _sample_clusters(analyses)

    contradictions, usage = await detect_contradictions(
        analyses, clusters, "query", mock_llm, mock_pm
    )

    assert len(contradictions) >= 1
    assert contradictions[0]["id"] == "contradiction_1"
    assert contradictions[0]["severity"] == "moderate"


@pytest.mark.asyncio
async def test_detect_contradictions_no_pairs():
    from app.agents.critic_agent import detect_contradictions

    # Single paper per cluster → no pairs
    analyses = [_make_paper("p1")]
    clusters = [{"id": "c0", "name": "Solo", "paper_ids": ["p1"], "paper_count": 1}]

    contradictions, usage = await detect_contradictions(
        analyses, clusters, "query", MagicMock(), MagicMock()
    )
    assert contradictions == []


# ── identify_gaps (LLM) ──


@pytest.mark.asyncio
async def test_identify_gaps():
    from app.agents.critic_agent import identify_gaps

    mock_llm = MagicMock()
    mock_llm.call = AsyncMock(return_value=(
        json.dumps({
            "gaps": [
                {
                    "description": "No low-resource evaluation",
                    "evidence": ["Most papers use English data"],
                    "priority": "high",
                    "related_cluster_ids": ["cluster_0"],
                    "suggested_direction": "Evaluate on low-resource languages",
                    "search_query": "low-resource NLP evaluation",
                }
            ]
        }),
        {"total_input": 100, "total_output": 50, "by_agent": {}},
    ))
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    analyses = _sample_analyses(6)
    clusters = _sample_clusters(analyses)
    trends = _sample_trends()

    gaps, usage = await identify_gaps(
        analyses, clusters, trends, "query", mock_llm, mock_pm
    )

    assert len(gaps) == 1
    assert gaps[0]["id"] == "gap_1"
    assert gaps[0]["priority"] == "high"
    assert gaps[0]["search_query"] == "low-resource NLP evaluation"


# ── summarize_limitations (LLM) ──


@pytest.mark.asyncio
async def test_summarize_limitations():
    from app.agents.critic_agent import summarize_limitations

    mock_llm = MagicMock()
    mock_llm.call = AsyncMock(return_value=(
        "## 方法学层面\n缺乏理论分析...\n\n## 数据层面\n数据集规模有限...",
        {"total_input": 100, "total_output": 50, "by_agent": {}},
    ))
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    analyses = _sample_analyses(4)
    summary, usage = await summarize_limitations(analyses, "query", mock_llm, mock_pm)

    assert "方法学" in summary
    assert len(summary) > 20


@pytest.mark.asyncio
async def test_summarize_limitations_no_data():
    from app.agents.critic_agent import summarize_limitations

    analyses = [_make_paper("p1", limitations=None)]
    summary, usage = await summarize_limitations(analyses, "query", MagicMock(), MagicMock())
    assert summary == ""


# ── critique_node ──


@pytest.mark.asyncio
async def test_critique_node_empty():
    """Empty analyses should return empty results."""
    state = {"paper_analyses": [], "user_query": "test"}
    result = await critique_node(state)

    assert result["quality_assessments"] == []
    assert result["contradictions"] == []
    assert result["research_gaps"] == []
    assert result["limitation_summary"] == ""
    assert result["feedback_search_queries"] == []
    assert result["current_phase"] == "outlining"


@pytest.mark.asyncio
async def test_critique_node_full():
    """Full critique with mocked LLM."""
    mock_llm = MagicMock()
    call_count = 0

    async def mock_call(prompt, agent_name, task_type, token_usage=None, **kw):
        nonlocal call_count
        call_count += 1

        if "评估" in prompt or "assessment" in task_type:
            if "矛盾" in prompt or "contradiction" in prompt:
                resp = {"contradictions": []}
            else:
                resp = {"assessments": [
                    {"paper_id": f"s2-{i}", "rigor_score": 7,
                     "justification": "OK", "strengths": [], "weaknesses": []}
                    for i in range(8)
                ]}
        elif "空白" in prompt or "gap" in task_type:
            resp = {"gaps": [
                {"description": "Gap 1", "evidence": ["e1"], "priority": "medium",
                 "related_cluster_ids": [], "suggested_direction": "dir", "search_query": None}
            ]}
        elif "局限" in prompt:
            return "局限性汇总文本。方法学层面存在不足。", \
                {"total_input": 50, "total_output": 30, "by_agent": {}}
        else:
            resp = {}

        return json.dumps(resp), {"total_input": 50, "total_output": 30, "by_agent": {}}

    mock_llm.call = AsyncMock(side_effect=mock_call)
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    analyses = _sample_analyses(8)
    clusters = _sample_clusters(analyses)
    trends = _sample_trends()

    state = {
        "paper_analyses": analyses,
        "topic_clusters": clusters,
        "research_trends": trends,
        "user_query": "deep learning methods",
    }

    result = await critique_node(state, llm=mock_llm, prompt_manager=mock_pm)

    assert len(result["quality_assessments"]) == 8
    assert all(0.0 <= a["quality_score"] <= 1.0 for a in result["quality_assessments"])
    assert isinstance(result["contradictions"], list)
    assert len(result["research_gaps"]) >= 1
    assert isinstance(result["limitation_summary"], str)
    assert isinstance(result["feedback_search_queries"], list)
    assert result["current_phase"] == "outlining"
    assert result["token_usage"] is not None


@pytest.mark.asyncio
async def test_critique_node_generates_feedback():
    """Critic should generate feedback queries when coverage gaps exist."""
    mock_llm = MagicMock()

    async def mock_call(prompt, agent_name, task_type, token_usage=None, **kw):
        if "局限" in prompt:
            return "Summary text", {"total_input": 50, "total_output": 30, "by_agent": {}}
        if "空白" in prompt or "gap" in task_type:
            resp = {"gaps": [
                {"description": "Gap", "evidence": [], "priority": "high",
                 "related_cluster_ids": [], "suggested_direction": "d",
                 "search_query": "supplementary search term"}
            ]}
        elif "矛盾" in prompt:
            resp = {"contradictions": []}
        else:
            resp = {"assessments": [
                {"paper_id": f"s2-{i}", "rigor_score": 6,
                 "justification": "ok", "strengths": [], "weaknesses": []}
                for i in range(5)
            ]}
        return json.dumps(resp), {"total_input": 50, "total_output": 30, "by_agent": {}}

    mock_llm.call = AsyncMock(side_effect=mock_call)
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    analyses = _sample_analyses(5)
    # Create a small cluster (< 3 papers) to trigger coverage gap
    clusters = [
        {"id": "c0", "name": "Small Cluster", "paper_ids": ["s2-0", "s2-1"],
         "paper_count": 2, "key_terms": ["small", "topic"]},
        {"id": "c1", "name": "Big Cluster", "paper_ids": ["s2-2", "s2-3", "s2-4"],
         "paper_count": 3, "key_terms": ["big"]},
    ]

    state = {
        "paper_analyses": analyses,
        "topic_clusters": clusters,
        "research_trends": _sample_trends(),
        "user_query": "test",
    }

    result = await critique_node(state, llm=mock_llm, prompt_manager=mock_pm)

    # Should have feedback queries from coverage gap + gap search_query
    assert len(result["feedback_search_queries"]) >= 1


# ═══════════════════════════════════════════════
#  _persist_quality_scores (DB write-back)
# ═══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_persist_quality_scores_writes_to_db(db_session):
    """quality_score and quality_notes are written to paper_analyses table."""
    from app.models.paper import Paper
    from app.models.paper_analysis import PaperAnalysis
    from app.models.project import Project

    # Create test data
    project = Project(
        id="proj-1",
        title="Test Project",
        user_query="test",
        status="critiquing",
    )
    db_session.add(project)

    paper = Paper(
        id="paper-1",
        title="Test Paper",
        authors=["Author A"],
        source="semantic_scholar",
    )
    db_session.add(paper)

    analysis = PaperAnalysis(
        id="analysis-1",
        project_id="proj-1",
        paper_id="paper-1",
        quality_score=None,
        quality_notes=None,
    )
    db_session.add(analysis)
    await db_session.commit()

    quality_assessments = [
        {"paper_id": "paper-1", "quality_score": 0.85, "justification": "High rigor"},
    ]

    # Patch async_session_factory inside critic_agent to return test session
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _mock_factory():
        yield db_session

    with patch(
        "app.models.database.async_session_factory",
        return_value=_mock_factory(),
    ):
        await _persist_quality_scores("proj-1", quality_assessments)

    # Verify
    await db_session.refresh(analysis)
    assert analysis.quality_score == 0.85
    assert analysis.quality_notes == "High rigor"


@pytest.mark.asyncio
async def test_persist_quality_scores_skips_missing_paper():
    """Papers not in DB are silently skipped (no error)."""
    quality_assessments = [
        {"paper_id": "nonexistent", "quality_score": 0.5, "justification": "Test"},
    ]

    # Should not raise — best-effort
    await _persist_quality_scores("proj-x", quality_assessments)


@pytest.mark.asyncio
async def test_persist_quality_scores_empty():
    """Empty assessments list is a no-op."""
    await _persist_quality_scores("proj-1", [])


@pytest.mark.asyncio
async def test_critique_node_calls_persist_with_project_id():
    """critique_node calls _persist_quality_scores when project_id is in state."""
    mock_llm = MagicMock()
    mock_llm.call = AsyncMock(return_value=(
        json.dumps({"assessments": [
            {"paper_id": "p1", "rigor_score": 0.8, "justification": "OK",
             "strengths": ["Good"], "weaknesses": []}
        ]}),
        {"total_input": 100, "total_output": 50, "by_agent": {}},
    ))
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    state = {
        "paper_analyses": [
            {"paper_id": "p1", "title": "P", "citation_count": 10, "venue": "arXiv",
             "findings": "F", "limitations": "L"},
        ],
        "topic_clusters": [],
        "research_trends": {"by_year": [], "by_topic": [], "emerging_topics": [], "narrative": ""},
        "user_query": "test",
        "project_id": "proj-test",
    }

    with patch("app.agents.critic_agent._persist_quality_scores", new_callable=AsyncMock) as mock_persist:
        result = await critique_node(state, llm=mock_llm, prompt_manager=mock_pm)

        mock_persist.assert_called_once_with("proj-test", result["quality_assessments"])


@pytest.mark.asyncio
async def test_critique_node_skips_persist_without_project_id():
    """critique_node skips DB write when project_id is not in state."""
    mock_llm = MagicMock()
    mock_llm.call = AsyncMock(return_value=(
        json.dumps({"assessments": [
            {"paper_id": "p1", "rigor_score": 0.7, "justification": "OK",
             "strengths": [], "weaknesses": []}
        ]}),
        {"total_input": 100, "total_output": 50, "by_agent": {}},
    ))
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    state = {
        "paper_analyses": [
            {"paper_id": "p1", "title": "P", "citation_count": 10, "venue": "arXiv",
             "findings": "F", "limitations": "L"},
        ],
        "topic_clusters": [],
        "research_trends": {"by_year": [], "by_topic": [], "emerging_topics": [], "narrative": ""},
        "user_query": "test",
        # No project_id
    }

    with patch("app.agents.critic_agent._persist_quality_scores", new_callable=AsyncMock) as mock_persist:
        await critique_node(state, llm=mock_llm, prompt_manager=mock_pm)

        mock_persist.assert_not_called()


# ── Rubric constants ──


def test_rubric_weights_completeness():
    """All expected output types have weight entries."""
    expected = {"full_review", "methodology_review", "gap_report", "trend_report", "research_roadmap"}
    assert set(RUBRIC_WEIGHTS.keys()) == expected


def test_rubric_weights_sum_to_one():
    for otype, weights in RUBRIC_WEIGHTS.items():
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.001, f"{otype} weights sum to {total}"


def test_rubric_dimensions():
    assert RUBRIC_DIMENSIONS == ("coherence", "depth", "rigor", "utility")


# ── assess_review ──


@pytest.mark.asyncio
async def test_assess_review_parses_scores():
    """assess_review correctly parses rubric scores from LLM."""
    mock_llm = AsyncMock()
    response = json.dumps({
        "scores": {"coherence": 8, "depth": 7, "rigor": 9, "utility": 6},
        "issues": [
            {"dimension": "utility", "location": "Conclusion",
             "description": "No future directions", "suggestion": "Add section"}
        ],
        "summary": "Solid but needs utility improvements."
    })
    mock_llm.call = AsyncMock(return_value=(response, {"total_input": 200, "total_output": 100}))

    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    scores, feedback, token_usage = await assess_review(
        full_draft="Full review text here...",
        user_query="test query",
        output_type="full_review",
        llm=mock_llm,
        prompt_manager=mock_pm,
    )

    assert scores["coherence"] == 8
    assert scores["depth"] == 7
    assert scores["rigor"] == 9
    assert scores["utility"] == 6
    assert "weighted" in scores
    # full_review: 8*0.30 + 7*0.25 + 9*0.25 + 6*0.20 = 2.4+1.75+2.25+1.2 = 7.6
    assert scores["weighted"] == 7.6
    assert len(feedback) == 1
    assert feedback[0]["dimension"] == "utility"


@pytest.mark.asyncio
async def test_assess_review_fallback_on_bad_json():
    """assess_review returns defaults on unparseable LLM response."""
    mock_llm = AsyncMock()
    mock_llm.call = AsyncMock(return_value=("not json at all", {"total_input": 10, "total_output": 5}))

    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    scores, feedback, _ = await assess_review(
        full_draft="Draft",
        user_query="q",
        output_type="full_review",
        llm=mock_llm,
        prompt_manager=mock_pm,
    )

    for d in RUBRIC_DIMENSIONS:
        assert scores[d] == 5
    assert scores["weighted"] == 5.0
    assert feedback == []


@pytest.mark.asyncio
async def test_assess_review_fills_missing_dimensions():
    """assess_review fills missing dimensions with default score 5."""
    mock_llm = AsyncMock()
    response = json.dumps({
        "scores": {"coherence": 9},  # only one dimension
        "issues": [],
        "summary": "Partial.",
    })
    mock_llm.call = AsyncMock(return_value=(response, {}))

    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    scores, _, _ = await assess_review(
        full_draft="Draft",
        user_query="q",
        output_type="full_review",
        llm=mock_llm,
        prompt_manager=mock_pm,
    )

    assert scores["coherence"] == 9
    assert scores["depth"] == 5
    assert scores["rigor"] == 5
    assert scores["utility"] == 5


# ── critique_node with review assessment ──


@pytest.mark.asyncio
async def test_critique_node_with_full_draft_runs_assessment():
    """critique_node calls assess_review when full_draft is present."""
    # LLM returns valid JSON for all calls
    quality_resp = json.dumps({"assessments": [
        {"paper_id": "p1", "rigor_score": 7, "justification": "ok",
         "strengths": ["good"], "weaknesses": []}
    ]})
    # With empty topic_clusters, detect_contradictions skips LLM call.
    # Actual LLM call sequence: quality → gaps → limitations → review_assessment
    gap_resp = json.dumps({"gaps": []})
    limitation_resp = "No common limitations."
    review_resp = json.dumps({
        "scores": {"coherence": 7, "depth": 6, "rigor": 8, "utility": 7},
        "issues": [],
        "summary": "Good."
    })

    responses = [quality_resp, gap_resp, limitation_resp, review_resp]
    call_count = 0

    async def mock_call(**kwargs):
        nonlocal call_count
        idx = min(call_count, len(responses) - 1)
        call_count += 1
        return responses[idx], {"total_input": 100, "total_output": 50, "by_agent": {}}

    mock_llm = AsyncMock()
    mock_llm.call = AsyncMock(side_effect=mock_call)
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    state = {
        "paper_analyses": [
            {"paper_id": "p1", "title": "P1", "citation_count": 10, "venue": "V",
             "findings": "F", "limitations": "L"},
        ],
        "topic_clusters": [],
        "research_trends": {"by_year": [], "by_topic": [], "emerging_topics": [], "narrative": ""},
        "user_query": "test",
        "full_draft": "This is the full review draft...",
        "output_types": ["full_review"],
    }

    with patch("app.agents.critic_agent._persist_quality_scores", new_callable=AsyncMock):
        result = await critique_node(state, llm=mock_llm, prompt_manager=mock_pm)

    assert "review_scores" in result
    assert "review_feedback" in result
    assert result["review_scores"]["coherence"] == 7


@pytest.mark.asyncio
async def test_critique_node_without_full_draft_skips_assessment():
    """critique_node does not call assess_review when full_draft is absent."""
    quality_resp = json.dumps({"assessments": [
        {"paper_id": "p1", "rigor_score": 7, "justification": "ok",
         "strengths": [], "weaknesses": []}
    ]})
    contradiction_resp = json.dumps({"contradictions": []})
    gap_resp = json.dumps({"gaps": []})
    limitation_resp = "No limitations."

    call_count = 0

    async def mock_call(**kwargs):
        nonlocal call_count
        call_count += 1
        responses = [quality_resp, contradiction_resp, gap_resp, limitation_resp]
        idx = min(call_count - 1, len(responses) - 1)
        return responses[idx], {"total_input": 50, "total_output": 25, "by_agent": {}}

    mock_llm = AsyncMock()
    mock_llm.call = AsyncMock(side_effect=mock_call)
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    state = {
        "paper_analyses": [
            {"paper_id": "p1", "title": "P1", "citation_count": 10, "venue": "V",
             "findings": "F", "limitations": "L"},
        ],
        "topic_clusters": [],
        "research_trends": {"by_year": [], "by_topic": [], "emerging_topics": [], "narrative": ""},
        "user_query": "test",
        # No full_draft
    }

    with patch("app.agents.critic_agent._persist_quality_scores", new_callable=AsyncMock):
        result = await critique_node(state, llm=mock_llm, prompt_manager=mock_pm)

    assert "review_scores" not in result
    assert "review_feedback" not in result


# ── review_assessment_node ──


@pytest.mark.asyncio
async def test_review_assessment_node_returns_scores():
    """review_assessment_node evaluates the draft and returns scores."""
    mock_llm = AsyncMock()
    response = json.dumps({
        "scores": {"coherence": 7, "depth": 6, "rigor": 8, "utility": 7},
        "issues": [{"dimension": "depth", "location": "S2", "description": "Shallow", "suggestion": "Deepen"}],
        "summary": "Decent."
    })
    mock_llm.call = AsyncMock(return_value=(response, {"total_input": 200, "total_output": 100}))
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    state = {
        "full_draft": "# Review\n\nContent here.",
        "user_query": "test query",
        "output_types": ["full_review"],
    }

    result = await review_assessment_node(state, llm=mock_llm, prompt_manager=mock_pm)

    assert result["review_scores"]["coherence"] == 7
    assert result["review_scores"]["depth"] == 6
    assert "weighted" in result["review_scores"]
    assert len(result["review_feedback"]) == 1
    assert result["current_phase"] == "review_assessment"


@pytest.mark.asyncio
async def test_review_assessment_node_no_draft():
    """review_assessment_node returns early when no full_draft."""
    state = {"user_query": "test"}

    result = await review_assessment_node(state)

    assert result["current_phase"] == "draft_review"
    assert "review_scores" not in result
