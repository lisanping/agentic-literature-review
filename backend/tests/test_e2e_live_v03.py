"""v0.3 End-to-end test with real LLM — requires OPENAI_API_KEY.

Run with:  pytest tests/test_e2e_live_v03.py -m live

These tests verify the full 6-Agent pipeline including actual LLM calls.
NOT run in CI.
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
async def test_live_analyst_agent():
    """Test Analyst Agent with real LLM on mock paper analyses."""
    from app.agents.analyst_agent import analyze_node

    state = {
        "user_query": "What are the recent advances in large language models?",
        "paper_analyses": [
            {
                "paper_id": "p1",
                "title": "GPT-4 Technical Report",
                "objective": "Present GPT-4 multimodal LLM",
                "methodology": "Large-scale pretraining + RLHF",
                "findings": "State-of-the-art on many benchmarks",
                "limitations": "High compute cost",
                "key_concepts": ["LLM", "GPT", "RLHF"],
                "method_category": "pretraining",
                "datasets": ["WebText", "BookCorpus"],
                "authors": ["OpenAI"],
                "year": 2023,
                "citation_count": 5000,
                "venue": "arXiv",
            },
            {
                "paper_id": "p2",
                "title": "LLaMA: Open Foundation Models",
                "objective": "Release open-source foundation models",
                "methodology": "Efficient pretraining on public data",
                "findings": "Competitive with GPT-3 at smaller scale",
                "limitations": "English-centric data",
                "key_concepts": ["LLM", "open-source", "efficient training"],
                "method_category": "pretraining",
                "datasets": ["CommonCrawl", "C4"],
                "authors": ["Meta AI"],
                "year": 2023,
                "citation_count": 3000,
                "venue": "arXiv",
            },
            {
                "paper_id": "p3",
                "title": "Code Llama: Open Foundation Models for Code",
                "objective": "Specialize LLM for code generation",
                "methodology": "Fine-tuning LLaMA on code data",
                "findings": "Strong code generation performance",
                "limitations": "Limited to popular languages",
                "key_concepts": ["code generation", "fine-tuning", "LLM"],
                "method_category": "fine-tuning",
                "datasets": ["CodeSearchNet", "GitHub"],
                "authors": ["Meta AI"],
                "year": 2024,
                "citation_count": 800,
                "venue": "ICML",
            },
        ],
        "output_language": "en",
    }

    result = await analyze_node(state)

    # Verify topic_clusters
    clusters = result.get("topic_clusters", [])
    assert len(clusters) >= 1
    for c in clusters:
        assert "name" in c
        assert "paper_ids" in c
        assert "key_terms" in c

    # Verify comparison_matrix
    matrix = result.get("comparison_matrix", {})
    assert "dimensions" in matrix
    assert "methods" in matrix

    # Verify timeline
    timeline = result.get("timeline", [])
    assert len(timeline) >= 1

    # Verify research_trends
    trends = result.get("research_trends", {})
    assert "by_year" in trends
    assert "narrative" in trends


@pytest.mark.asyncio
async def test_live_critic_agent():
    """Test Critic Agent with real LLM on mock paper analyses."""
    from app.agents.critic_agent import critique_node

    state = {
        "user_query": "deep learning for NLP",
        "paper_analyses": [
            {
                "paper_id": "p1",
                "title": "BERT: Pre-training of Deep Bidirectional Transformers",
                "objective": "Pre-train deep bidirectional representations",
                "methodology": "Masked language modeling + next sentence prediction",
                "findings": "SOTA on 11 NLP tasks",
                "limitations": "High computational cost",
                "key_concepts": ["BERT", "pretraining", "transformer"],
                "method_category": "pretraining",
                "datasets": ["BookCorpus", "Wikipedia"],
                "authors": ["Devlin et al."],
                "year": 2019,
                "citation_count": 80000,
                "venue": "NAACL",
            },
            {
                "paper_id": "p2",
                "title": "Attention Is All You Need",
                "objective": "Propose transformer architecture",
                "methodology": "Self-attention mechanism",
                "findings": "Outperforms RNNs on translation",
                "limitations": "Quadratic complexity",
                "key_concepts": ["transformer", "self-attention"],
                "method_category": "architecture",
                "datasets": ["WMT"],
                "authors": ["Vaswani et al."],
                "year": 2017,
                "citation_count": 100000,
                "venue": "NeurIPS",
            },
        ],
        "topic_clusters": [
            {"id": "c0", "name": "Transformer Models", "paper_ids": ["p1", "p2"], "paper_count": 2, "key_terms": ["transformer"]},
        ],
        "research_trends": {
            "by_year": [{"year": 2017, "count": 1, "citations_sum": 100000}, {"year": 2019, "count": 1, "citations_sum": 80000}],
            "by_topic": [{"topic": "transformer", "trend": "rising", "yearly_counts": []}],
            "emerging_topics": [],
            "narrative": "Transformers dominate NLP.",
        },
        "output_language": "en",
    }

    result = await critique_node(state)

    # Verify quality_assessments
    qa = result.get("quality_assessments", [])
    assert len(qa) >= 1
    for a in qa:
        assert "quality_score" in a
        assert 0 <= a["quality_score"] <= 1

    # Verify research_gaps
    gaps = result.get("research_gaps", [])
    assert isinstance(gaps, list)

    # Verify limitation_summary
    assert isinstance(result.get("limitation_summary", ""), str)


@pytest.mark.asyncio
async def test_live_writer_with_analyst_critic():
    """Test Writer Agent with analyst/critic context using real LLM."""
    from app.agents.writer_agent import generate_outline_node, write_review_node

    state = {
        "user_query": "transformer models in NLP",
        "paper_analyses": [
            {
                "paper_id": "p1",
                "title": "BERT",
                "objective": "Pre-train bidirectional representations",
                "methodology": "MLM + NSP",
                "findings": "SOTA on NLP tasks",
                "limitations": "Compute cost",
                "key_concepts": ["BERT"],
                "authors": ["Devlin"],
                "year": 2019,
            },
        ],
        "output_types": ["full_review"],
        "output_language": "en",
        "citation_style": "apa",
        "topic_clusters": [
            {"id": "c0", "name": "Pre-training", "paper_ids": ["p1"], "paper_count": 1, "key_terms": ["BERT", "pre-training"]},
        ],
        "comparison_matrix": {"title": "M", "dimensions": [], "methods": [], "narrative": ""},
        "contradictions": [],
        "research_trends": {"by_year": [], "by_topic": [], "emerging_topics": [], "narrative": ""},
        "research_gaps": [
            {"description": "No multilingual study", "priority": "high", "evidence": [], "suggested_direction": "Multilingual BERT"},
        ],
        "limitation_summary": "Limited to English.",
        "quality_assessments": [
            {"paper_id": "p1", "quality_score": 0.9},
        ],
    }

    # Generate outline
    outline_result = await generate_outline_node(state)
    assert "outline" in outline_result
    outline = outline_result["outline"]
    assert "sections" in outline
    assert len(outline["sections"]) >= 2

    # Write review
    state["outline"] = outline
    write_result = await write_review_node(state)
    assert "full_draft" in write_result
    assert len(write_result["full_draft"]) > 100
    assert len(write_result.get("references", [])) >= 1
