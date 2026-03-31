"""Critic Agent — quality assessment, contradiction detection, gap analysis.

Components (aligned with v0.3 §2.2):
  - Quality Scorer: LLM rigor assessment + bibliometric normalization
  - Contradiction Detector: same-cluster paper pair comparison
  - Gap Identifier: cluster coverage + trend analysis → research gaps
  - Limitation Summarizer: aggregate paper limitations → cohesive narrative
  - Feedback Generator: coverage/time/method gaps → supplementary search queries

Quality score formula:
  quality_score = 0.6 × llm_rigor_score + 0.3 × normalized_citations + 0.1 × venue_tier
"""

import json
from itertools import combinations

import structlog
from sqlalchemy import select, update

from app.agents.registry import agent_registry
from app.agents.state import ReviewState
from app.services.llm import LLMRouter
from app.services.prompt_manager import PromptManager

logger = structlog.stdlib.get_logger()

QUALITY_BATCH_SIZE = 10
MAX_PAIRS_PER_CLUSTER = 10
MIN_CLUSTER_PAPERS_FOR_FEEDBACK = 3

# Rubric dimension weights by output type (shared with writer_agent)
RUBRIC_WEIGHTS = {
    "full_review":        {"coherence": 0.30, "depth": 0.25, "rigor": 0.25, "utility": 0.20},
    "methodology_review": {"coherence": 0.20, "depth": 0.30, "rigor": 0.30, "utility": 0.20},
    "gap_report":         {"coherence": 0.15, "depth": 0.35, "rigor": 0.20, "utility": 0.30},
    "trend_report":       {"coherence": 0.25, "depth": 0.30, "rigor": 0.20, "utility": 0.25},
    "research_roadmap":   {"coherence": 0.15, "depth": 0.25, "rigor": 0.15, "utility": 0.45},
}

RUBRIC_DIMENSIONS = ("coherence", "depth", "rigor", "utility")


# ── JSON Parsing Utility ──


def _parse_json_response(text: str) -> dict | list | None:
    """Parse LLM response as JSON, handling markdown code fences."""
    text = text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, IndexError):
        logger.warning("critic.json_parse_failed", preview=text[:200])
        return None


# ── Paper ID helper ──


def _get_paper_id(paper: dict) -> str:
    """Extract a stable paper identifier."""
    return paper.get("paper_id") or paper.get("s2_id") or paper.get("title", "")[:50]


# ── 1. Quality Assessment ──


def compute_quality_score(
    llm_rigor_score: float,
    citation_count: int,
    max_citations: int,
    venue_tier: float = 0.2,
) -> float:
    """Compute composite quality score per the rubric.

    quality_score = 0.6 × llm_rigor + 0.3 × normalized_citations + 0.1 × venue_tier

    Args:
        llm_rigor_score: LLM score 0-10, normalized to 0-1 internally.
        citation_count: Paper's citation count.
        max_citations: Maximum citations in the paper set.
        venue_tier: Venue quality 0-1 (1.0=top, 0.5=mid, 0.2=unknown).
    """
    rigor_normalized = min(max(llm_rigor_score / 10.0, 0.0), 1.0)
    citations_normalized = min(citation_count / max_citations, 1.0) if max_citations > 0 else 0.0
    score = 0.6 * rigor_normalized + 0.3 * citations_normalized + 0.1 * venue_tier
    return round(min(max(score, 0.0), 1.0), 3)


async def assess_quality_batch(
    papers: list[dict],
    user_query: str,
    max_citations: int,
    llm: LLMRouter,
    prompt_manager: PromptManager,
    token_usage: dict | None = None,
) -> tuple[list[dict], dict]:
    """Assess quality for a batch of papers via LLM.

    Returns:
        (quality_assessments_list, updated_token_usage)
    """
    prompt = prompt_manager.render(
        "critic",
        "quality_assessment",
        user_query=user_query,
        papers=papers,
    )

    response_text, token_usage = await llm.call(
        prompt=prompt,
        agent_name="critic",
        task_type="quality_assessment",
        token_usage=token_usage,
    )

    parsed = _parse_json_response(response_text)
    llm_assessments = parsed.get("assessments", []) if parsed else []

    # Build lookup from LLM response
    llm_map: dict[str, dict] = {}
    for a in llm_assessments:
        pid = a.get("paper_id", "")
        llm_map[pid] = a

    assessments = []
    for paper in papers:
        pid = _get_paper_id(paper)
        llm_data = llm_map.get(pid, {})
        rigor_score = llm_data.get("rigor_score", 5)
        citation_count = paper.get("citation_count", 0) or 0

        quality_score = compute_quality_score(
            llm_rigor_score=rigor_score,
            citation_count=citation_count,
            max_citations=max_citations,
        )

        assessments.append({
            "paper_id": pid,
            "quality_score": quality_score,
            "llm_rigor_score": rigor_score / 10.0,
            "normalized_citations": min(citation_count / max_citations, 1.0) if max_citations > 0 else 0.0,
            "venue_tier": 0.2,
            "justification": llm_data.get("justification", ""),
            "strengths": llm_data.get("strengths", []),
            "weaknesses": llm_data.get("weaknesses", []),
        })

    return assessments, token_usage


async def assess_all_papers(
    analyses: list[dict],
    user_query: str,
    llm: LLMRouter,
    prompt_manager: PromptManager,
    token_usage: dict | None = None,
) -> tuple[list[dict], dict]:
    """Assess quality for all papers in batches.

    Returns:
        (all_quality_assessments, updated_token_usage)
    """
    all_citations = [a.get("citation_count", 0) or 0 for a in analyses]
    max_citations = max(all_citations) if all_citations else 1

    all_assessments: list[dict] = []

    for i in range(0, len(analyses), QUALITY_BATCH_SIZE):
        batch = analyses[i : i + QUALITY_BATCH_SIZE]
        batch_assessments, token_usage = await assess_quality_batch(
            papers=batch,
            user_query=user_query,
            max_citations=max_citations,
            llm=llm,
            prompt_manager=prompt_manager,
            token_usage=token_usage,
        )
        all_assessments.extend(batch_assessments)

    logger.info("critic.quality_assessed", papers=len(all_assessments))
    return all_assessments, token_usage


# ── 2. Contradiction Detection ──


def build_cluster_paper_pairs(
    analyses: list[dict],
    topic_clusters: list[dict],
) -> list[tuple[str, dict, dict]]:
    """Build paper pairs within same cluster for contradiction checking.

    Limits to MAX_PAIRS_PER_CLUSTER per cluster.

    Returns:
        List of (cluster_name, paper_a, paper_b) tuples.
    """
    # Build paper lookup
    paper_map: dict[str, dict] = {}
    for a in analyses:
        pid = _get_paper_id(a)
        paper_map[pid] = a

    pairs: list[tuple[str, dict, dict]] = []
    for cluster in topic_clusters:
        cluster_name = cluster.get("name", "Unknown")
        paper_ids = cluster.get("paper_ids", [])
        cluster_papers = [paper_map[pid] for pid in paper_ids if pid in paper_map]

        if len(cluster_papers) < 2:
            continue

        # Generate pairs, limited
        cluster_pairs = list(combinations(cluster_papers, 2))[:MAX_PAIRS_PER_CLUSTER]
        for pa, pb in cluster_pairs:
            pairs.append((cluster_name, pa, pb))

    return pairs


async def detect_contradictions(
    analyses: list[dict],
    topic_clusters: list[dict],
    user_query: str,
    llm: LLMRouter,
    prompt_manager: PromptManager,
    token_usage: dict | None = None,
) -> tuple[list[dict], dict]:
    """Detect contradictions between papers in the same cluster.

    Returns:
        (contradictions_list, updated_token_usage)
    """
    all_pairs = build_cluster_paper_pairs(analyses, topic_clusters)

    if not all_pairs:
        return [], token_usage or {}

    # Group pairs by cluster for batch LLM calls
    by_cluster: dict[str, list[tuple[dict, dict]]] = {}
    for cluster_name, pa, pb in all_pairs:
        by_cluster.setdefault(cluster_name, []).append((pa, pb))

    all_contradictions: list[dict] = []
    contradiction_counter = 0

    for cluster_name, pairs in by_cluster.items():
        paper_pairs = [
            {
                "paper_a": {
                    "title": pa.get("title", ""),
                    "methodology": pa.get("methodology"),
                    "findings": pa.get("findings"),
                    "datasets": pa.get("datasets", []),
                    "paper_id": _get_paper_id(pa),
                },
                "paper_b": {
                    "title": pb.get("title", ""),
                    "methodology": pb.get("methodology"),
                    "findings": pb.get("findings"),
                    "datasets": pb.get("datasets", []),
                    "paper_id": _get_paper_id(pb),
                },
            }
            for pa, pb in pairs
        ]

        prompt = prompt_manager.render(
            "critic",
            "contradiction_detection",
            user_query=user_query,
            cluster_name=cluster_name,
            paper_pairs=paper_pairs,
        )

        response_text, token_usage = await llm.call(
            prompt=prompt,
            agent_name="critic",
            task_type="quality_assessment",  # reuse routing
            token_usage=token_usage,
        )

        parsed = _parse_json_response(response_text)
        if parsed and "contradictions" in parsed:
            for c in parsed["contradictions"]:
                contradiction_counter += 1
                c["id"] = f"contradiction_{contradiction_counter}"
                all_contradictions.append(c)

    logger.info("critic.contradictions_found", count=len(all_contradictions))
    return all_contradictions, token_usage


# ── 3. Research Gap Identification ──


async def identify_gaps(
    analyses: list[dict],
    topic_clusters: list[dict],
    research_trends: dict,
    user_query: str,
    llm: LLMRouter,
    prompt_manager: PromptManager,
    token_usage: dict | None = None,
) -> tuple[list[dict], dict]:
    """Identify research gaps based on cluster coverage and trends.

    Returns:
        (research_gaps_list, updated_token_usage)
    """
    # Prepare trend info
    by_topic = research_trends.get("by_topic", [])

    # Prepare limitations
    limitations = [
        {"title": a.get("title", ""), "limitations": a.get("limitations")}
        for a in analyses
        if a.get("limitations")
    ]

    prompt = prompt_manager.render(
        "critic",
        "gap_identification",
        user_query=user_query,
        clusters=topic_clusters,
        trends=by_topic,
        limitations=limitations,
    )

    response_text, token_usage = await llm.call(
        prompt=prompt,
        agent_name="critic",
        task_type="gap_identification",
        token_usage=token_usage,
    )

    parsed = _parse_json_response(response_text)
    gaps_raw = parsed.get("gaps", []) if parsed else []

    gaps = []
    for i, g in enumerate(gaps_raw):
        gaps.append({
            "id": f"gap_{i + 1}",
            "description": g.get("description", ""),
            "evidence": g.get("evidence", []),
            "priority": g.get("priority", "medium"),
            "related_cluster_ids": g.get("related_cluster_ids", []),
            "suggested_direction": g.get("suggested_direction", ""),
            "search_query": g.get("search_query"),
        })

    logger.info("critic.gaps_identified", count=len(gaps))
    return gaps, token_usage


# ── 4. Limitation Summary ──


async def summarize_limitations(
    analyses: list[dict],
    user_query: str,
    llm: LLMRouter,
    prompt_manager: PromptManager,
    token_usage: dict | None = None,
) -> tuple[str, dict]:
    """Aggregate paper limitations into a cohesive narrative.

    Returns:
        (limitation_summary_text, updated_token_usage)
    """
    papers_with_limitations = [
        {
            "title": a.get("title", ""),
            "methodology": a.get("methodology"),
            "limitations": a.get("limitations"),
            "method_category": a.get("method_category"),
        }
        for a in analyses
        if a.get("limitations")
    ]

    if not papers_with_limitations:
        return "", token_usage or {}

    prompt = prompt_manager.render(
        "critic",
        "limitation_summary",
        user_query=user_query,
        papers=papers_with_limitations,
    )

    response_text, token_usage = await llm.call(
        prompt=prompt,
        agent_name="critic",
        task_type="gap_identification",  # reuse routing
        token_usage=token_usage,
    )

    # This prompt returns plain text, not JSON
    summary = response_text.strip()
    logger.info("critic.limitations_summarized", chars=len(summary))
    return summary, token_usage


# ── 5. Feedback Query Generator ──


def generate_feedback_queries(
    topic_clusters: list[dict],
    research_gaps: list[dict],
    research_trends: dict,
) -> list[str]:
    """Generate supplementary search queries based on coverage gaps.

    Triggers when:
    1. A cluster has fewer than MIN_CLUSTER_PAPERS_FOR_FEEDBACK papers
       (coverage gap)
    2. A research gap has an explicit search_query suggestion
    3. A trending topic has no recent papers (time gap)
    """
    queries: list[str] = []

    # 1. Coverage gaps: clusters with too few papers
    for cluster in topic_clusters:
        if cluster.get("paper_count", 0) < MIN_CLUSTER_PAPERS_FOR_FEEDBACK:
            name = cluster.get("name", "")
            key_terms = cluster.get("key_terms", [])
            if key_terms:
                queries.append(" ".join(key_terms[:3]))
            elif name:
                queries.append(name)

    # 2. Research gap search suggestions
    for gap in research_gaps:
        sq = gap.get("search_query")
        if sq:
            queries.append(sq)

    # 3. Time gaps: rising topics with no recent counts
    import datetime
    current_year = datetime.datetime.now(datetime.timezone.utc).year
    for topic in research_trends.get("by_topic", []):
        if topic.get("trend") == "rising":
            yearly = topic.get("yearly_counts", [])
            recent_years = [yc for yc in yearly if yc.get("year", 0) >= current_year - 2]
            if not recent_years:
                queries.append(topic.get("topic", ""))

    # Deduplicate
    seen: set[str] = set()
    unique_queries: list[str] = []
    for q in queries:
        q_lower = q.strip().lower()
        if q_lower and q_lower not in seen:
            seen.add(q_lower)
            unique_queries.append(q.strip())

    logger.info("critic.feedback_queries", count=len(unique_queries))
    return unique_queries


# ── Critic Agent Node ──


# ── 6. Review-Level Assessment (Rubric-based) ──


async def assess_review(
    full_draft: str,
    user_query: str,
    output_type: str,
    llm: LLMRouter,
    prompt_manager: PromptManager,
    token_usage: dict | None = None,
) -> tuple[dict, list[dict], dict]:
    """Assess the generated review using the shared rubric.

    This provides an independent Critic-side evaluation of the review
    output, using the same rubric dimensions as the Writer's self-assessment
    but from an independent reviewer perspective.

    Returns:
        (scores_dict, feedback_list, updated_token_usage)
    """
    weights = RUBRIC_WEIGHTS.get(output_type, RUBRIC_WEIGHTS["full_review"])

    prompt = prompt_manager.render(
        "critic",
        "review_assessment",
        user_query=user_query,
        full_draft=full_draft[:12000],
        weights=weights,
    )

    response_text, token_usage = await llm.call(
        prompt=prompt,
        agent_name="critic",
        task_type="review_assessment",
        token_usage=token_usage,
    )

    parsed = _parse_json_response(response_text)
    if not parsed or not isinstance(parsed, dict):
        default_scores = {d: 5 for d in RUBRIC_DIMENSIONS}
        default_scores["weighted"] = 5.0
        return default_scores, [], token_usage

    scores = parsed.get("scores", {})
    for d in RUBRIC_DIMENSIONS:
        if d not in scores:
            scores[d] = 5
    weighted = sum(scores.get(d, 5) * weights.get(d, 0.25) for d in RUBRIC_DIMENSIONS)
    scores["weighted"] = round(weighted, 2)

    feedback = parsed.get("issues", [])

    logger.info(
        "critic.review_assessment_complete",
        scores=scores,
        issues_count=len(feedback),
    )

    return scores, feedback, token_usage


async def critique_node(
    state: ReviewState,
    llm: LLMRouter | None = None,
    prompt_manager: PromptManager | None = None,
) -> dict:
    """Critic Agent node function.

    Inputs from state:
        - paper_analyses: paper analysis dicts from Reader
        - topic_clusters: cluster results from Analyst
        - research_trends: trend results from Analyst
        - user_query: original research question

    Returns:
        Partial state with quality_assessments, contradictions,
        research_gaps, limitation_summary, feedback_search_queries,
        token_usage, current_phase.
    """
    llm = llm or LLMRouter()
    prompt_manager = prompt_manager or PromptManager()

    analyses = state.get("paper_analyses", [])
    topic_clusters = state.get("topic_clusters", [])
    research_trends = state.get("research_trends", {})
    user_query = state.get("user_query", "")
    token_usage = state.get("token_usage")

    if not analyses:
        return {
            "quality_assessments": [],
            "contradictions": [],
            "research_gaps": [],
            "limitation_summary": "",
            "feedback_search_queries": [],
            "current_phase": "outlining",
            "token_usage": token_usage,
        }

    # 1. Quality assessment (batched)
    quality_assessments, token_usage = await assess_all_papers(
        analyses, user_query, llm, prompt_manager, token_usage
    )

    # 2. Contradiction detection (same-cluster pairs)
    contradictions, token_usage = await detect_contradictions(
        analyses, topic_clusters, user_query, llm, prompt_manager, token_usage
    )

    # 3. Research gap identification
    research_gaps, token_usage = await identify_gaps(
        analyses, topic_clusters, research_trends, user_query,
        llm, prompt_manager, token_usage
    )

    # 4. Limitation summary
    limitation_summary, token_usage = await summarize_limitations(
        analyses, user_query, llm, prompt_manager, token_usage
    )

    # 5. Feedback query generation (algorithmic)
    feedback_queries = generate_feedback_queries(
        topic_clusters, research_gaps, research_trends
    )

    # 6. Persist quality scores to DB (best-effort, non-blocking)
    project_id = state.get("project_id")
    if project_id and quality_assessments:
        await _persist_quality_scores(project_id, quality_assessments)

    logger.info(
        "agent.critique_complete",
        assessments=len(quality_assessments),
        contradictions=len(contradictions),
        gaps=len(research_gaps),
        feedback_queries=len(feedback_queries),
    )

    updates = {
        "quality_assessments": quality_assessments,
        "contradictions": contradictions,
        "research_gaps": research_gaps,
        "limitation_summary": limitation_summary,
        "feedback_search_queries": feedback_queries,
        "token_usage": token_usage,
        "current_phase": "outlining",
    }

    # ── Review-level assessment (only when full_draft exists) ──
    full_draft = state.get("full_draft")
    if full_draft:
        output_types = state.get("output_types", ["full_review"])
        output_type = output_types[0] if output_types else "full_review"

        review_scores, review_feedback, token_usage = await assess_review(
            full_draft=full_draft,
            user_query=user_query,
            output_type=output_type,
            llm=llm,
            prompt_manager=prompt_manager,
            token_usage=token_usage,
        )
        updates["review_scores"] = review_scores
        updates["review_feedback"] = review_feedback
        updates["token_usage"] = token_usage

    return updates


async def _persist_quality_scores(
    project_id: str,
    quality_assessments: list[dict],
) -> None:
    """Write quality_score and quality_notes to paper_analyses rows.

    Best-effort: logs warning on failure but does not raise, since
    the scores are already in the workflow state and will be used
    by downstream agents regardless.
    """
    try:
        from app.models.database import async_session_factory
        from app.models.paper_analysis import PaperAnalysis

        async with async_session_factory() as session:
            for qa in quality_assessments:
                paper_id = qa.get("paper_id")
                if not paper_id:
                    continue

                score = qa.get("quality_score")
                notes = qa.get("justification", "")

                stmt = (
                    update(PaperAnalysis)
                    .where(
                        PaperAnalysis.project_id == project_id,
                        PaperAnalysis.paper_id == paper_id,
                    )
                    .values(quality_score=score, quality_notes=notes)
                )
                await session.execute(stmt)

            await session.commit()

        logger.info(
            "critic.quality_scores_persisted",
            project_id=project_id,
            count=len(quality_assessments),
        )
    except Exception:
        logger.warning(
            "critic.quality_scores_persist_failed",
            project_id=project_id,
            exc_info=True,
        )


agent_registry.register("critique", critique_node)
