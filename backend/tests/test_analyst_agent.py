"""Tests for Analyst Agent — clustering, comparison matrix, network, trends."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.agents.analyst_agent import (
    _parse_json_response,
    cluster_papers_by_similarity,
    build_citation_network,
    build_yearly_data,
    compute_trend_stats,
    analyze_node,
    _assign_paper_role,
    _identify_key_papers,
    _identify_bridge_papers,
    _cluster_by_concepts,
    _find_closest_group,
)


# ── Test fixtures ──


def _make_paper(
    paper_id: str,
    title: str = "Paper",
    year: int = 2023,
    method_category: str | None = None,
    key_concepts: list[str] | None = None,
    methodology: str | None = None,
    findings: str | None = None,
    citation_count: int = 10,
    relations: list[dict] | None = None,
    objective: str | None = None,
    datasets: list[str] | None = None,
    limitations: str | None = None,
) -> dict:
    return {
        "paper_id": paper_id,
        "title": title,
        "year": year,
        "method_category": method_category,
        "key_concepts": key_concepts or [],
        "methodology": methodology,
        "findings": findings,
        "citation_count": citation_count,
        "relations": relations or [],
        "objective": objective,
        "datasets": datasets or [],
        "limitations": limitations,
    }


def _sample_analyses(n: int = 10) -> list[dict]:
    """Generate n sample paper analyses across categories."""
    categories = ["supervised", "unsupervised", "reinforcement", "supervised", "unsupervised"]
    concepts_pool = [
        ["transformer", "attention"],
        ["clustering", "embedding"],
        ["reward", "policy"],
        ["CNN", "convolution"],
        ["GAN", "generation"],
    ]
    return [
        _make_paper(
            paper_id=f"s2-{i}",
            title=f"Paper {i}: {categories[i % len(categories)]}",
            year=2020 + (i % 4),
            method_category=categories[i % len(categories)],
            key_concepts=concepts_pool[i % len(concepts_pool)],
            methodology=f"Method {i}",
            findings=f"Finding {i}",
            citation_count=10 * (i + 1),
            objective=f"Objective {i}",
        )
        for i in range(n)
    ]


# ── _parse_json_response ──


def test_parse_json_clean():
    text = '{"name": "Test Cluster", "summary": "A summary", "key_terms": ["a"]}'
    result = _parse_json_response(text)
    assert result["name"] == "Test Cluster"


def test_parse_json_markdown_fenced():
    text = '```json\n{"name": "Fenced"}\n```'
    result = _parse_json_response(text)
    assert result["name"] == "Fenced"


def test_parse_json_invalid():
    result = _parse_json_response("not json at all")
    assert result is None


# ── cluster_papers_by_similarity ──


def test_cluster_by_method_category():
    """Papers with different method_category should be grouped separately."""
    papers = [
        _make_paper("p1", method_category="supervised", key_concepts=["a"]),
        _make_paper("p2", method_category="supervised", key_concepts=["a"]),
        _make_paper("p3", method_category="unsupervised", key_concepts=["b"]),
        _make_paper("p4", method_category="unsupervised", key_concepts=["b"]),
        _make_paper("p5", method_category="reinforcement", key_concepts=["c"]),
    ]
    groups = cluster_papers_by_similarity(papers)
    assert len(groups) >= 2
    total = sum(len(g) for g in groups)
    assert total == 5


def test_cluster_uncategorized_distributed():
    """Uncategorized papers should be distributed to closest group."""
    papers = [
        _make_paper("p1", method_category="supervised", key_concepts=["a", "b"]),
        _make_paper("p2", method_category="unsupervised", key_concepts=["c"]),
        _make_paper("p3", method_category=None, key_concepts=["a"]),  # closer to p1
    ]
    groups = cluster_papers_by_similarity(papers)
    total = sum(len(g) for g in groups)
    assert total == 3


def test_cluster_no_categories_uses_concepts():
    """Without method_category, should use concept-based clustering."""
    papers = [
        _make_paper("p1", key_concepts=["a", "b"]),
        _make_paper("p2", key_concepts=["a", "c"]),
        _make_paper("p3", key_concepts=["d", "e"]),
        _make_paper("p4", key_concepts=["d", "f"]),
    ]
    groups = cluster_papers_by_similarity(papers)
    assert len(groups) >= 1
    total = sum(len(g) for g in groups)
    assert total == 4


def test_cluster_empty():
    groups = cluster_papers_by_similarity([])
    assert groups == []


# ── _find_closest_group ──


def test_find_closest_group():
    paper = _make_paper("p1", key_concepts=["x", "y"])
    groups = [
        [_make_paper("g0", key_concepts=["a", "b"])],
        [_make_paper("g1", key_concepts=["x", "z"])],
    ]
    result = _find_closest_group(paper, groups)
    assert result is groups[1]  # overlap with "x"


# ── _cluster_by_concepts ──


def test_cluster_by_concepts_merges():
    papers = [
        _make_paper("p1", key_concepts=["a"]),
        _make_paper("p2", key_concepts=["a"]),
        _make_paper("p3", key_concepts=["b"]),
    ]
    groups = _cluster_by_concepts(papers, n_clusters=2)
    assert len(groups) == 2
    total = sum(len(g) for g in groups)
    assert total == 3


# ── build_citation_network ──


def test_build_citation_network_basic():
    analyses = [
        _make_paper("p1", citation_count=100, year=2020),
        _make_paper("p2", citation_count=50, year=2023,
                    relations=[{"target_id": "p1", "type": "cites"}]),
        _make_paper("p3", citation_count=10, year=2025),
    ]
    clusters = [{"id": "c0", "paper_ids": ["p1", "p2", "p3"]}]

    network = build_citation_network(analyses, clusters)

    assert len(network["nodes"]) == 3
    assert len(network["edges"]) == 1
    assert network["edges"][0]["source"] == "p2"
    assert network["edges"][0]["target"] == "p1"
    assert "p1" in network["key_papers"]  # highest cited


def test_build_citation_network_empty():
    network = build_citation_network([], [])
    assert network["nodes"] == []
    assert network["edges"] == []


# ── _assign_paper_role ──


def test_assign_role_recent():
    role = _assign_paper_role(citation_count=5, max_citations=100, year=2026)
    assert role == "recent"


def test_assign_role_foundational():
    role = _assign_paper_role(citation_count=80, max_citations=100, year=2015)
    assert role == "foundational"


def test_assign_role_bridge():
    role = _assign_paper_role(citation_count=30, max_citations=100, year=2018)
    assert role == "bridge"


def test_assign_role_peripheral():
    role = _assign_paper_role(citation_count=5, max_citations=100, year=2018)
    assert role == "peripheral"


# ── _identify_key_papers ──


def test_identify_key_papers():
    nodes = [
        {"id": "p1", "citation_count": 50},
        {"id": "p2", "citation_count": 200},
        {"id": "p3", "citation_count": 100},
    ]
    keys = _identify_key_papers(nodes, top_n=2)
    assert keys == ["p2", "p3"]


# ── _identify_bridge_papers ──


def test_identify_bridge_papers():
    nodes = [{"id": "p1"}, {"id": "p2"}, {"id": "p3"}]
    edges = [
        {"source": "p2", "target": "p1"},
        {"source": "p2", "target": "p3"},
    ]
    cluster_map = {"p1": "c0", "p2": "c0", "p3": "c1"}
    bridges = _identify_bridge_papers(nodes, edges, cluster_map)
    assert "p2" in bridges  # connects c0 and c1


def test_identify_bridge_papers_no_bridges():
    nodes = [{"id": "p1"}, {"id": "p2"}]
    edges = [{"source": "p1", "target": "p2"}]
    cluster_map = {"p1": "c0", "p2": "c0"}
    bridges = _identify_bridge_papers(nodes, edges, cluster_map)
    assert bridges == []


# ── build_yearly_data ──


def test_build_yearly_data():
    analyses = [
        _make_paper("p1", year=2020),
        _make_paper("p2", year=2020),
        _make_paper("p3", year=2022),
    ]
    yearly = build_yearly_data(analyses)
    assert len(yearly) == 2
    assert yearly[0]["year"] == 2020
    assert yearly[0]["paper_count"] == 2
    assert yearly[1]["year"] == 2022


def test_build_yearly_data_no_years():
    analyses = [_make_paper("p1", year=None)]
    yearly = build_yearly_data(analyses)
    assert yearly == []


# ── compute_trend_stats ──


def test_compute_trend_stats():
    analyses = [
        _make_paper("p1", year=2020, citation_count=10),
        _make_paper("p2", year=2020, citation_count=20),
        _make_paper("p3", year=2022, citation_count=5),
    ]
    clusters = [
        {"id": "c0", "name": "Topic A", "paper_ids": ["p1", "p2"],
         "paper_count": 2, "key_terms": ["term1"]},
        {"id": "c1", "name": "Topic B", "paper_ids": ["p3"],
         "paper_count": 1, "key_terms": ["term2"]},
    ]

    by_year, by_topic = compute_trend_stats(analyses, clusters)

    assert len(by_year) == 2
    assert by_year[0]["year"] == 2020
    assert by_year[0]["count"] == 2
    assert by_year[0]["citations_sum"] == 30

    assert len(by_topic) == 2
    assert by_topic[0]["name"] == "Topic A"
    assert by_topic[0]["paper_count"] == 2


# ── name_cluster (LLM) ──


@pytest.mark.asyncio
async def test_name_cluster():
    from app.agents.analyst_agent import name_cluster

    mock_llm = MagicMock()
    mock_llm.call = AsyncMock(return_value=(
        json.dumps({
            "name": "Transformer Methods",
            "summary": "Papers focused on transformer architectures.",
            "key_terms": ["transformer", "attention"],
        }),
        {"total_input": 100, "total_output": 50, "by_agent": {}},
    ))
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    papers = [_make_paper("p1", title="Paper 1"), _make_paper("p2", title="Paper 2")]
    cluster, usage = await name_cluster(papers, "cluster_0", "test query", mock_llm, mock_pm)

    assert cluster["id"] == "cluster_0"
    assert cluster["name"] == "Transformer Methods"
    assert cluster["paper_count"] == 2
    assert "transformer" in cluster["key_terms"]


# ── build_topic_clusters (LLM) ──


@pytest.mark.asyncio
async def test_build_topic_clusters():
    from app.agents.analyst_agent import build_topic_clusters

    mock_llm = MagicMock()
    mock_llm.call = AsyncMock(return_value=(
        json.dumps({
            "name": "Generated Cluster",
            "summary": "A cluster summary",
            "key_terms": ["term"],
        }),
        {"total_input": 100, "total_output": 50, "by_agent": {}},
    ))
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    analyses = _sample_analyses(6)
    clusters, usage = await build_topic_clusters(analyses, "test query", mock_llm, mock_pm)

    assert len(clusters) >= 2
    total_papers = sum(c["paper_count"] for c in clusters)
    assert total_papers == 6
    assert all(c["id"].startswith("cluster_") for c in clusters)


# ── build_comparison_matrix (LLM) ──


@pytest.mark.asyncio
async def test_build_comparison_matrix():
    from app.agents.analyst_agent import build_comparison_matrix

    mock_llm = MagicMock()
    mock_llm.call = AsyncMock(return_value=(
        json.dumps({
            "dimensions": [{"key": "accuracy", "label": "Accuracy", "unit": "%"}],
            "methods": [{"name": "MethodA", "category": "supervised",
                        "paper_id": "p1", "values": {"accuracy": 95.0}}],
            "narrative": "MethodA is superior.",
        }),
        {"total_input": 100, "total_output": 50, "by_agent": {}},
    ))
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    analyses = [_make_paper("p1", method_category="supervised", methodology="MethodA")]
    matrix, usage = await build_comparison_matrix(analyses, "query", mock_llm, mock_pm)

    assert matrix["title"] == "方法对比矩阵"
    assert len(matrix["dimensions"]) == 1
    assert len(matrix["methods"]) == 1
    assert matrix["narrative"] == "MethodA is superior."


@pytest.mark.asyncio
async def test_build_comparison_matrix_no_methods():
    from app.agents.analyst_agent import build_comparison_matrix

    analyses = [_make_paper("p1")]  # no method info
    matrix, usage = await build_comparison_matrix(analyses, "query", MagicMock(), MagicMock())

    assert matrix["methods"] == []
    assert matrix["dimensions"] == []


# ── build_timeline (LLM) ──


@pytest.mark.asyncio
async def test_build_timeline():
    from app.agents.analyst_agent import build_timeline

    mock_llm = MagicMock()
    mock_llm.call = AsyncMock(return_value=(
        json.dumps({
            "milestones": [
                {"year": 2020, "milestone": "Breakthrough X", "paper_ids": ["p1"],
                 "key_event": "First application of X"},
                {"year": 2022, "milestone": None, "paper_ids": ["p2"],
                 "key_event": None},
            ],
        }),
        {"total_input": 100, "total_output": 50, "by_agent": {}},
    ))
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    analyses = [
        _make_paper("p1", year=2020),
        _make_paper("p2", year=2022),
    ]
    timeline, usage = await build_timeline(analyses, "query", mock_llm, mock_pm)

    assert len(timeline) == 2
    assert timeline[0]["year"] == 2020
    assert timeline[0]["milestone"] == "Breakthrough X"
    assert timeline[1]["milestone"] is None


# ── analyze_trends (LLM) ──


@pytest.mark.asyncio
async def test_analyze_trends():
    from app.agents.analyst_agent import analyze_trends

    mock_llm = MagicMock()
    mock_llm.call = AsyncMock(return_value=(
        json.dumps({
            "topic_trends": [
                {"topic": "Topic A", "trend": "rising"},
            ],
            "emerging_topics": ["multimodal learning"],
            "narrative": "Research is trending upward.",
        }),
        {"total_input": 100, "total_output": 50, "by_agent": {}},
    ))
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    analyses = _sample_analyses(6)
    clusters = [{"id": "c0", "name": "Topic A", "paper_ids": ["s2-0", "s2-1"],
                 "paper_count": 2, "key_terms": ["a"]}]
    trends, usage = await analyze_trends(analyses, clusters, "query", mock_llm, mock_pm)

    assert len(trends["by_year"]) >= 1
    assert "multimodal learning" in trends["emerging_topics"]
    assert trends["narrative"] == "Research is trending upward."


# ── analyze_node ──


@pytest.mark.asyncio
async def test_analyze_node_skip_few_papers():
    """Should skip analysis when fewer than MIN_PAPERS_FOR_ANALYSIS papers."""
    state = {"paper_analyses": [_make_paper("p1")], "user_query": "test"}
    result = await analyze_node(state)

    assert result["topic_clusters"] == []
    assert result["comparison_matrix"]["methods"] == []
    assert result["citation_network"]["nodes"] == []
    assert result["timeline"] == []
    assert result["research_trends"]["by_year"] == []
    assert result["current_phase"] == "critiquing"


@pytest.mark.asyncio
async def test_analyze_node_full():
    """Full analysis with mocked LLM."""
    mock_llm = MagicMock()
    call_count = 0

    async def mock_call(prompt, agent_name, task_type, token_usage=None, **kw):
        nonlocal call_count
        call_count += 1
        # Return different responses based on task
        if "聚类" in prompt or "topic_clustering" in task_type:
            resp = {"name": f"Cluster {call_count}", "summary": "Summary", "key_terms": ["t"]}
        elif "对比" in prompt or "comparison" in task_type:
            if "趋势" in prompt or "trend" in prompt:
                resp = {"topic_trends": [], "emerging_topics": ["emerging"],
                        "narrative": "trend narrative"}
            else:
                resp = {"dimensions": [], "methods": [], "narrative": "matrix narrative"}
        elif "里程碑" in prompt or "milestone" in prompt:
            resp = {"milestones": []}
        else:
            resp = {"topic_trends": [], "emerging_topics": [], "narrative": "narrative"}
        return json.dumps(resp), {"total_input": 50, "total_output": 30, "by_agent": {}}

    mock_llm.call = AsyncMock(side_effect=mock_call)
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    state = {
        "paper_analyses": _sample_analyses(8),
        "user_query": "deep learning methods",
    }

    result = await analyze_node(state, llm=mock_llm, prompt_manager=mock_pm)

    assert len(result["topic_clusters"]) >= 2
    assert "title" in result["comparison_matrix"]
    assert "nodes" in result["citation_network"]
    assert len(result["citation_network"]["nodes"]) == 8
    assert isinstance(result["timeline"], list)
    assert "by_year" in result["research_trends"]
    assert result["current_phase"] == "critiquing"
    assert result["token_usage"] is not None


@pytest.mark.asyncio
async def test_analyze_node_empty():
    """Empty paper_analyses should return empty results."""
    state = {"paper_analyses": [], "user_query": "test"}
    result = await analyze_node(state)
    assert result["topic_clusters"] == []
    assert result["current_phase"] == "critiquing"


@pytest.mark.asyncio
async def test_analyze_node_caps_large_input():
    """Papers exceeding MAX_PAPERS should be capped."""
    mock_llm = MagicMock()
    mock_llm.call = AsyncMock(return_value=(
        json.dumps({"name": "C", "summary": "S", "key_terms": ["t"]}),
        {"total_input": 50, "total_output": 30, "by_agent": {}},
    ))
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    # Create 210 papers (exceeds MAX_PAPERS_FOR_ANALYSIS=200)
    large_analyses = _sample_analyses(210)
    state = {"paper_analyses": large_analyses, "user_query": "test"}

    result = await analyze_node(state, llm=mock_llm, prompt_manager=mock_pm)

    # Should still produce results (capped internally)
    assert result["current_phase"] == "critiquing"
    assert result["token_usage"] is not None
