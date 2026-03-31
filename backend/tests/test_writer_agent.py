"""Tests for Writer Agent — outline, section writing, references, coherence.

v0.3 additions:
  - Citation weight strategy tests
  - Topic cluster–aware outline tests
  - Specialized output type tests
  - Research gaps section generation tests
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.agents.writer_agent import (
    apply_citation_weights,
    build_references_list,
    generate_outline_node,
    revise_review_node,
    write_review_node,
    write_specialized_output,
    review_coherence,
    compute_weighted_score,
    _build_gaps_section,
    _parse_json_response,
    QUALITY_HIGH_THRESHOLD,
    QUALITY_LOW_THRESHOLD,
    SPECIALIZED_OUTPUT_TYPES,
    RUBRIC_WEIGHTS,
    RUBRIC_DIMENSIONS,
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


# ═══════════════════════════════════════════════
#  v0.3: Citation Weight Strategy
# ═══════════════════════════════════════════════


def test_apply_citation_weights_sorts_by_quality():
    analyses = [
        {"paper_id": "low", "title": "Low Quality"},
        {"paper_id": "high", "title": "High Quality"},
        {"paper_id": "mid", "title": "Mid Quality"},
    ]
    quality_assessments = [
        {"paper_id": "low", "quality_score": 0.2},
        {"paper_id": "high", "quality_score": 0.9},
        {"paper_id": "mid", "quality_score": 0.5},
    ]

    result = apply_citation_weights(analyses, quality_assessments)
    assert result[0]["paper_id"] == "high"  # tier 0 (≥0.7)
    assert result[1]["paper_id"] == "mid"   # tier 1 (0.3-0.7)
    assert result[2]["paper_id"] == "low"   # tier 2 (<0.3)


def test_apply_citation_weights_no_assessments():
    analyses = [{"paper_id": "p1"}, {"paper_id": "p2"}]
    result = apply_citation_weights(analyses, [])
    assert result == analyses  # unchanged


def test_apply_citation_weights_missing_paper():
    analyses = [
        {"paper_id": "p1", "title": "Known"},
        {"paper_id": "p2", "title": "Unknown"},
    ]
    quality_assessments = [
        {"paper_id": "p1", "quality_score": 0.9},
    ]

    result = apply_citation_weights(analyses, quality_assessments)
    # p1 (0.9 → tier 0) comes first, p2 (default 0.5 → tier 1) comes second
    assert result[0]["paper_id"] == "p1"
    assert result[1]["paper_id"] == "p2"


# ═══════════════════════════════════════════════
#  v0.3: _build_gaps_section
# ═══════════════════════════════════════════════


def test_build_gaps_section_with_gaps():
    gaps = [
        {
            "description": "Missing multilingual evaluation",
            "priority": "high",
            "evidence": ["Most papers use English only"],
            "suggested_direction": "Evaluate on low-resource languages",
        },
        {
            "description": "No standardized benchmark",
            "priority": "medium",
            "evidence": [],
            "suggested_direction": "Propose benchmark suite",
        },
    ]
    result = _build_gaps_section(gaps, "Papers share common data limitations.")

    assert "Missing multilingual evaluation" in result
    assert "高" in result  # high priority
    assert "中" in result  # medium priority
    assert "Evaluate on low-resource languages" in result
    assert "共性局限总结" in result
    assert "common data limitations" in result


def test_build_gaps_section_empty():
    result = _build_gaps_section([], "")
    assert "暂无" in result


# ═══════════════════════════════════════════════
#  v0.3: Outline with topic_clusters
# ═══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_generate_outline_node_with_clusters():
    """Outline generation passes topic_clusters to prompt."""
    captured_kwargs = {}

    mock_llm = MagicMock()
    mock_llm.call = AsyncMock(return_value=(
        json.dumps({
            "title": "Clustered Review",
            "sections": [
                {"heading": "Supervised Methods", "description": "Cluster 1", "relevant_paper_indices": [1]},
                {"heading": "Unsupervised Methods", "description": "Cluster 2", "relevant_paper_indices": [2]},
            ],
        }),
        {"total_input": 200, "total_output": 100, "by_agent": {}},
    ))
    mock_pm = MagicMock()

    def capture_render(agent, template, **kwargs):
        captured_kwargs.update(kwargs)
        return "prompt"

    mock_pm.render.side_effect = capture_render

    state = {
        "user_query": "deep learning",
        "paper_analyses": [
            {"title": "Paper 1", "objective": "O1"},
            {"title": "Paper 2", "objective": "O2"},
        ],
        "output_types": ["full_review"],
        "output_language": "zh",
        "topic_clusters": [
            {"id": "c0", "name": "Supervised", "paper_count": 1, "key_terms": ["supervised"]},
            {"id": "c1", "name": "Unsupervised", "paper_count": 1, "key_terms": ["unsupervised"]},
        ],
    }

    result = await generate_outline_node(state, llm=mock_llm, prompt_manager=mock_pm)

    # Verify clusters were passed to the prompt
    assert "topic_clusters" in captured_kwargs
    assert len(captured_kwargs["topic_clusters"]) == 2
    assert result["outline"]["title"] == "Clustered Review"


# ═══════════════════════════════════════════════
#  v0.3: Write review with analyst/critic data
# ═══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_write_review_node_with_analyst_critic_data():
    """Write review passes comparison_matrix, contradictions, research_trends to sections."""
    captured_render_calls = []

    call_count = 0

    async def mock_call(prompt, agent_name, task_type, token_usage=None, **kw):
        nonlocal call_count
        call_count += 1
        return f"Section {call_count} content.", {
            "total_input": 100, "total_output": 50, "by_agent": {},
        }

    mock_llm = MagicMock()
    mock_llm.call = AsyncMock(side_effect=mock_call)
    mock_pm = MagicMock()

    def capture_render(agent, template, **kwargs):
        captured_render_calls.append({"agent": agent, "template": template, **kwargs})
        return "prompt"

    mock_pm.render.side_effect = capture_render

    state = {
        "user_query": "test",
        "outline": {
            "title": "Review",
            "sections": [
                {"heading": "Intro", "description": "Background", "relevant_paper_indices": [1]},
            ],
        },
        "paper_analyses": [
            {"title": "P1", "paper_id": "1", "authors": ["A"], "year": 2024},
        ],
        "citation_style": "apa",
        "output_language": "zh",
        "output_types": ["full_review"],
        "comparison_matrix": {"title": "Matrix", "dimensions": [], "methods": [], "narrative": "Method comparison."},
        "contradictions": [{"topic": "Speed", "claim_a": "Fast", "claim_b": "Slow", "severity": "minor"}],
        "research_trends": {"by_year": [], "by_topic": [], "narrative": "Rising trend."},
        "research_gaps": [],
        "quality_assessments": [],
    }

    result = await write_review_node(state, llm=mock_llm, prompt_manager=mock_pm)

    # Verify section_writing render call received analyst/critic context
    section_calls = [c for c in captured_render_calls if c["template"] == "section_writing"]
    assert len(section_calls) >= 1
    assert "comparison_matrix" in section_calls[0]
    assert "contradictions" in section_calls[0]
    assert "research_trends" in section_calls[0]
    assert result["current_phase"] == "draft_review"


@pytest.mark.asyncio
async def test_write_review_node_auto_gaps_section():
    """Full review auto-appends Research Gaps section when gaps exist."""
    call_count = 0

    async def mock_call(prompt, agent_name, task_type, token_usage=None, **kw):
        nonlocal call_count
        call_count += 1
        return f"Section content {call_count}.", {
            "total_input": 100, "total_output": 50, "by_agent": {},
        }

    mock_llm = MagicMock()
    mock_llm.call = AsyncMock(side_effect=mock_call)
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    state = {
        "user_query": "test",
        "outline": {
            "title": "Review",
            "sections": [
                {"heading": "Intro", "description": "Background", "relevant_paper_indices": []},
            ],
        },
        "paper_analyses": [
            {"title": "P1", "paper_id": "1", "authors": ["A"], "year": 2024},
        ],
        "citation_style": "apa",
        "output_language": "zh",
        "output_types": ["full_review"],
        "research_gaps": [
            {"description": "Gap 1", "priority": "high", "evidence": ["e1"],
             "suggested_direction": "direction"},
        ],
        "limitation_summary": "Common limitation text.",
        "quality_assessments": [],
    }

    result = await write_review_node(state, llm=mock_llm, prompt_manager=mock_pm)

    assert "Research Gaps" in result["full_draft"]
    assert "Gap 1" in result["full_draft"]
    assert "Common limitation text" in result["full_draft"]
    # sections: 1 outline section + 1 auto-generated gaps section = 2
    assert len(result["draft_sections"]) == 2


# ═══════════════════════════════════════════════
#  v0.3: Specialized Output Types
# ═══════════════════════════════════════════════


@pytest.mark.asyncio
async def test_write_specialized_methodology_review():
    mock_llm = MagicMock()
    mock_llm.call = AsyncMock(return_value=(
        "# Methodology Review\n\nComparison of methods...",
        {"total_input": 200, "total_output": 150, "by_agent": {}},
    ))
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    state = {
        "comparison_matrix": {"title": "Matrix", "dimensions": [], "methods": [], "narrative": ""},
    }

    content, usage = await write_specialized_output(
        output_type="methodology_review",
        analyses=[{"title": "P1", "paper_id": "1"}],
        user_query="test",
        output_language="zh",
        state=state,
        llm=mock_llm,
        prompt_manager=mock_pm,
    )

    assert "Methodology Review" in content
    mock_pm.render.assert_called_once()
    render_kwargs = mock_pm.render.call_args
    assert render_kwargs[0] == ("writer", "methodology_review")


@pytest.mark.asyncio
async def test_write_specialized_gap_report():
    mock_llm = MagicMock()
    mock_llm.call = AsyncMock(return_value=(
        "# Gap Report\n\nResearch gaps identified...",
        {"total_input": 200, "total_output": 150, "by_agent": {}},
    ))
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    state = {
        "research_gaps": [{"description": "Gap"}],
        "contradictions": [],
        "limitation_summary": "Limitations.",
        "topic_clusters": [],
    }

    content, usage = await write_specialized_output(
        output_type="gap_report",
        analyses=[],
        user_query="test",
        output_language="en",
        state=state,
        llm=mock_llm,
        prompt_manager=mock_pm,
    )

    assert "Gap Report" in content


@pytest.mark.asyncio
async def test_write_review_node_specialized_output():
    """write_review_node uses specialized writer for methodology_review."""
    mock_llm = MagicMock()
    mock_llm.call = AsyncMock(return_value=(
        "# Methodology Review\n\nDetailed method comparison.",
        {"total_input": 200, "total_output": 150, "by_agent": {}},
    ))
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    state = {
        "user_query": "test",
        "outline": {},
        "paper_analyses": [
            {"title": "P1", "paper_id": "1", "authors": ["A"], "year": 2024},
        ],
        "citation_style": "apa",
        "output_language": "zh",
        "output_types": ["methodology_review"],
        "comparison_matrix": {"title": "M", "dimensions": [], "methods": [], "narrative": ""},
        "quality_assessments": [],
    }

    result = await write_review_node(state, llm=mock_llm, prompt_manager=mock_pm)

    assert "Methodology Review" in result["full_draft"]
    assert result["current_phase"] == "draft_review"
    assert len(result["references"]) == 1


@pytest.mark.asyncio
async def test_write_review_node_citation_weight_order():
    """High-quality papers should appear first in references."""
    call_count = 0

    async def mock_call(prompt, agent_name, task_type, token_usage=None, **kw):
        nonlocal call_count
        call_count += 1
        return "Content.", {"total_input": 50, "total_output": 30, "by_agent": {}}

    mock_llm = MagicMock()
    mock_llm.call = AsyncMock(side_effect=mock_call)
    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    state = {
        "user_query": "test",
        "outline": {
            "title": "Review",
            "sections": [{"heading": "S", "description": "D", "relevant_paper_indices": []}],
        },
        "paper_analyses": [
            {"title": "Low Paper", "paper_id": "low", "authors": ["A"], "year": 2024},
            {"title": "High Paper", "paper_id": "high", "authors": ["B"], "year": 2023},
        ],
        "citation_style": "apa",
        "output_language": "zh",
        "output_types": ["full_review"],
        "quality_assessments": [
            {"paper_id": "low", "quality_score": 0.2},
            {"paper_id": "high", "quality_score": 0.9},
        ],
    }

    result = await write_review_node(state, llm=mock_llm, prompt_manager=mock_pm)

    # References should be ordered: high first, low last
    refs = result["references"]
    assert refs[0]["paper_id"] == "high"
    assert refs[1]["paper_id"] == "low"


def test_specialized_output_types_set():
    """Verify the set of supported specialized output types."""
    assert "methodology_review" in SPECIALIZED_OUTPUT_TYPES
    assert "gap_report" in SPECIALIZED_OUTPUT_TYPES
    assert "trend_report" in SPECIALIZED_OUTPUT_TYPES
    assert "research_roadmap" in SPECIALIZED_OUTPUT_TYPES
    assert "full_review" not in SPECIALIZED_OUTPUT_TYPES


# ── Rubric: compute_weighted_score ──


def test_compute_weighted_score_full_review():
    scores = {"coherence": 8, "depth": 6, "rigor": 7, "utility": 7}
    weights = RUBRIC_WEIGHTS["full_review"]
    result = compute_weighted_score(scores, weights)
    # 8*0.30 + 6*0.25 + 7*0.25 + 7*0.20 = 2.4 + 1.5 + 1.75 + 1.4 = 7.05
    assert result == 7.05


def test_compute_weighted_score_gap_report():
    scores = {"coherence": 5, "depth": 9, "rigor": 6, "utility": 8}
    weights = RUBRIC_WEIGHTS["gap_report"]
    result = compute_weighted_score(scores, weights)
    # 5*0.15 + 9*0.35 + 6*0.20 + 8*0.30 = 0.75 + 3.15 + 1.2 + 2.4 = 7.5
    assert result == 7.5


def test_compute_weighted_score_defaults_missing():
    """Missing dimensions default to 5."""
    scores = {"coherence": 10}
    weights = RUBRIC_WEIGHTS["full_review"]
    result = compute_weighted_score(scores, weights)
    # 10*0.30 + 5*0.25 + 5*0.25 + 5*0.20 = 3.0 + 1.25 + 1.25 + 1.0 = 6.5
    assert result == 6.5


def test_rubric_weights_all_output_types():
    """Every output type's weights sum to 1.0."""
    for otype, weights in RUBRIC_WEIGHTS.items():
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.001, f"{otype} weights sum to {total}"


def test_rubric_dimensions_tuple():
    assert len(RUBRIC_DIMENSIONS) == 4
    assert "coherence" in RUBRIC_DIMENSIONS
    assert "depth" in RUBRIC_DIMENSIONS
    assert "rigor" in RUBRIC_DIMENSIONS
    assert "utility" in RUBRIC_DIMENSIONS


# ── Rubric: review_coherence (rubric-based) ──


@pytest.mark.asyncio
async def test_review_coherence_rubric_format():
    """Coherence review returns rubric-based scores and issues."""
    mock_llm = AsyncMock()
    rubric_response = json.dumps({
        "scores": {"coherence": 8, "depth": 6, "rigor": 7, "utility": 7},
        "issues": [{"dimension": "depth", "location": "Section 3",
                     "description": "Lacks cross-paper comparison",
                     "suggestion": "Add comparison paragraph"}],
        "summary": "Good overall."
    })
    mock_llm.call = AsyncMock(return_value=(rubric_response, {"total_input": 100, "total_output": 50}))

    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    review, token_usage = await review_coherence(
        full_draft="Test draft content",
        user_query="test query",
        llm=mock_llm,
        prompt_manager=mock_pm,
        output_type="full_review",
    )

    assert "scores" in review
    assert review["scores"]["coherence"] == 8
    assert review["scores"]["depth"] == 6
    assert "weighted" in review["scores"]
    assert len(review["issues"]) == 1
    assert review["issues"][0]["dimension"] == "depth"
    # Back-compat
    assert "overall_quality" in review

    # Verify weights were passed to prompt render
    render_call = mock_pm.render.call_args
    assert render_call.kwargs.get("weights") or "weights" in str(render_call)


@pytest.mark.asyncio
async def test_review_coherence_fallback():
    """Coherence review falls back to defaults on invalid JSON."""
    mock_llm = AsyncMock()
    mock_llm.call = AsyncMock(return_value=("not valid json", {"total_input": 10, "total_output": 5}))

    mock_pm = MagicMock()
    mock_pm.render.return_value = "prompt"

    review, _ = await review_coherence(
        full_draft="Test",
        user_query="test",
        llm=mock_llm,
        prompt_manager=mock_pm,
    )

    assert review["scores"]["coherence"] == 5
    assert review["scores"]["depth"] == 5
    assert "weighted" in review["scores"]
