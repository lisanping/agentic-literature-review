"""Analyst Agent — topic clustering, comparison matrix, citation network, trends.

Components (aligned with v0.3 §2.1):
  - Topic Clusterer: Chroma embedding clustering + LLM naming/summary
  - Comparison Matrix Builder: structured extraction from paper analyses + LLM
  - Citation Network Builder: paper relations → directed graph + LLM role tagging
  - Timeline Builder: year-based paper ordering + LLM milestone detection
  - Trend Analyzer: yearly statistics + LLM trend interpretation

Paper count thresholds:
  - < 5: skip analysis (insufficient data)
  - 5-50: full analysis
  - 50-200: batch processing (20 per batch), merge results
  - > 200: top 100 by relevance, warn user
"""

import json
from collections import defaultdict

import structlog

from app.agents.registry import agent_registry
from app.agents.state import ReviewState
from app.services.llm import LLMRouter, update_token_usage
from app.services.prompt_manager import PromptManager

logger = structlog.stdlib.get_logger()

MIN_PAPERS_FOR_ANALYSIS = 5
BATCH_SIZE = 20
MAX_PAPERS_FOR_ANALYSIS = 200


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
        logger.warning("analyst.json_parse_failed", preview=text[:200])
        return None


# ── 1. Topic Clustering ──


def cluster_papers_by_similarity(
    analyses: list[dict],
    n_clusters: int | None = None,
) -> list[list[dict]]:
    """Cluster papers by keyword/concept overlap (algorithmic).

    Uses a simple similarity-based grouping when Chroma embeddings are
    unavailable.  Falls back to method_category grouping, then to
    key_concept overlap.

    Returns a list of groups, each group being a list of paper-analysis dicts.
    """
    # Strategy 1: group by method_category if available
    by_category: dict[str, list[dict]] = defaultdict(list)
    uncategorized: list[dict] = []

    for a in analyses:
        cat = a.get("method_category")
        if cat:
            by_category[cat].append(a)
        else:
            uncategorized.append(a)

    if len(by_category) >= 2:
        groups = list(by_category.values())
        # Distribute uncategorized papers to closest group by concept overlap
        for paper in uncategorized:
            best_group = _find_closest_group(paper, groups)
            best_group.append(paper)
        return groups

    # Strategy 2: group by key_concept overlap
    return _cluster_by_concepts(analyses, n_clusters)


def _find_closest_group(paper: dict, groups: list[list[dict]]) -> list[dict]:
    """Find the group with highest concept overlap to a paper."""
    paper_concepts = set(paper.get("key_concepts") or [])
    best_score = -1
    best_group = groups[0]
    for group in groups:
        group_concepts: set[str] = set()
        for p in group:
            group_concepts.update(p.get("key_concepts") or [])
        score = len(paper_concepts & group_concepts)
        if score > best_score:
            best_score = score
            best_group = group
    return best_group


def _cluster_by_concepts(
    analyses: list[dict],
    n_clusters: int | None = None,
) -> list[list[dict]]:
    """Cluster by key concept overlap using greedy merging."""
    if not analyses:
        return []

    # Start: each paper in its own cluster
    clusters: list[list[dict]] = [[a] for a in analyses]
    target = n_clusters or max(2, min(len(analyses) // 3, 7))

    while len(clusters) > target:
        # Find the two clusters with highest concept overlap
        best_i, best_j, best_score = 0, 1, -1
        for i in range(len(clusters)):
            concepts_i: set[str] = set()
            for p in clusters[i]:
                concepts_i.update(p.get("key_concepts") or [])
            for j in range(i + 1, len(clusters)):
                concepts_j: set[str] = set()
                for p in clusters[j]:
                    concepts_j.update(p.get("key_concepts") or [])
                score = len(concepts_i & concepts_j)
                if score > best_score:
                    best_score = score
                    best_i, best_j = i, j
        # Merge
        clusters[best_i].extend(clusters[best_j])
        clusters.pop(best_j)

    return clusters


async def name_cluster(
    cluster_papers: list[dict],
    cluster_id: str,
    user_query: str,
    llm: LLMRouter,
    prompt_manager: PromptManager,
    token_usage: dict | None = None,
) -> tuple[dict, dict]:
    """Use LLM to generate a name and summary for a paper cluster.

    Returns:
        (cluster_dict, updated_token_usage)
    """
    prompt = prompt_manager.render(
        "analyst",
        "topic_clustering",
        user_query=user_query,
        papers=cluster_papers,
    )

    response_text, token_usage = await llm.call(
        prompt=prompt,
        agent_name="analyst",
        task_type="topic_clustering",
        token_usage=token_usage,
    )

    parsed = _parse_json_response(response_text)

    paper_ids = [
        p.get("paper_id") or p.get("s2_id") or p.get("title", "")[:50]
        for p in cluster_papers
    ]
    years = [p.get("year") for p in cluster_papers if p.get("year")]
    avg_year = sum(years) / len(years) if years else None

    cluster_dict = {
        "id": cluster_id,
        "name": parsed.get("name", f"Cluster {cluster_id}") if parsed else f"Cluster {cluster_id}",
        "summary": parsed.get("summary", "") if parsed else "",
        "paper_ids": paper_ids,
        "paper_count": len(cluster_papers),
        "avg_year": round(avg_year, 1) if avg_year else None,
        "key_terms": parsed.get("key_terms", []) if parsed else [],
    }

    return cluster_dict, token_usage


async def build_topic_clusters(
    analyses: list[dict],
    user_query: str,
    llm: LLMRouter,
    prompt_manager: PromptManager,
    token_usage: dict | None = None,
) -> tuple[list[dict], dict]:
    """Build topic clusters: algorithmic grouping + LLM naming.

    Returns:
        (topic_clusters_list, updated_token_usage)
    """
    groups = cluster_papers_by_similarity(analyses)
    clusters: list[dict] = []

    for i, group in enumerate(groups):
        cluster_dict, token_usage = await name_cluster(
            cluster_papers=group,
            cluster_id=f"cluster_{i}",
            user_query=user_query,
            llm=llm,
            prompt_manager=prompt_manager,
            token_usage=token_usage,
        )
        clusters.append(cluster_dict)

    logger.info("analyst.clusters_built", count=len(clusters))
    return clusters, token_usage


# ── 2. Comparison Matrix ──


async def build_comparison_matrix(
    analyses: list[dict],
    user_query: str,
    llm: LLMRouter,
    prompt_manager: PromptManager,
    token_usage: dict | None = None,
) -> tuple[dict, dict]:
    """Build a method comparison matrix from paper analyses + LLM.

    Returns:
        (comparison_matrix_dict, updated_token_usage)
    """
    # Filter papers that have method info
    papers_with_methods = [
        a for a in analyses
        if a.get("method_category") or a.get("methodology")
    ]

    if not papers_with_methods:
        return {"title": "方法对比矩阵", "dimensions": [], "methods": [], "narrative": ""}, token_usage or {}

    prompt = prompt_manager.render(
        "analyst",
        "comparison_matrix",
        user_query=user_query,
        papers=papers_with_methods,
    )

    response_text, token_usage = await llm.call(
        prompt=prompt,
        agent_name="analyst",
        task_type="comparison",
        token_usage=token_usage,
    )

    parsed = _parse_json_response(response_text)

    matrix = {
        "title": "方法对比矩阵",
        "dimensions": parsed.get("dimensions", []) if parsed else [],
        "methods": parsed.get("methods", []) if parsed else [],
        "narrative": parsed.get("narrative", "") if parsed else "",
    }

    logger.info("analyst.matrix_built", methods=len(matrix["methods"]))
    return matrix, token_usage


# ── 3. Citation Network ──


def build_citation_network(
    analyses: list[dict],
    topic_clusters: list[dict],
) -> dict:
    """Build citation network from paper analyses (algorithmic).

    Constructs nodes from papers and edges from inter-paper relations.
    Assigns roles based on citation count and cluster membership.
    """
    # Build cluster lookup
    paper_cluster_map: dict[str, str] = {}
    for cluster in topic_clusters:
        for pid in cluster.get("paper_ids", []):
            paper_cluster_map[pid] = cluster["id"]

    # Collect citation counts for role assignment
    all_citation_counts = [
        a.get("citation_count", 0) or 0 for a in analyses
    ]
    max_citations = max(all_citation_counts) if all_citation_counts else 1

    nodes = []
    edges = []
    paper_id_set: set[str] = set()

    for a in analyses:
        paper_id = a.get("paper_id") or a.get("s2_id") or a.get("title", "")[:50]
        paper_id_set.add(paper_id)
        citation_count = a.get("citation_count", 0) or 0
        year = a.get("year")

        # Determine role
        role = _assign_paper_role(
            citation_count=citation_count,
            max_citations=max_citations,
            year=year,
        )

        nodes.append({
            "id": paper_id,
            "title": a.get("title", ""),
            "year": year,
            "cluster_id": paper_cluster_map.get(paper_id),
            "citation_count": citation_count,
            "role": role,
        })

    # Build edges from relations (if available from Reader)
    for a in analyses:
        paper_id = a.get("paper_id") or a.get("s2_id") or a.get("title", "")[:50]
        relations = a.get("relations") or []
        for rel in relations:
            target_id = rel.get("target_id") or rel.get("paper_id")
            if target_id and target_id in paper_id_set:
                edges.append({
                    "source": paper_id,
                    "target": target_id,
                    "relation": rel.get("type", "cites"),
                })

    # Identify key papers (top cited) and bridge papers (multi-cluster connections)
    key_papers = _identify_key_papers(nodes, top_n=3)
    bridge_papers = _identify_bridge_papers(nodes, edges, paper_cluster_map)

    network = {
        "nodes": nodes,
        "edges": edges,
        "key_papers": key_papers,
        "bridge_papers": bridge_papers,
    }

    logger.info(
        "analyst.network_built",
        nodes=len(nodes),
        edges=len(edges),
    )
    return network


def _assign_paper_role(
    citation_count: int,
    max_citations: int,
    year: int | None,
) -> str:
    """Assign a role to a paper based on citations and recency."""
    import datetime
    current_year = datetime.datetime.now(datetime.timezone.utc).year

    if year and year >= current_year - 1:
        return "recent"
    ratio = citation_count / max_citations if max_citations > 0 else 0
    if ratio >= 0.6:
        return "foundational"
    if ratio >= 0.2:
        return "bridge"
    return "peripheral"


def _identify_key_papers(nodes: list[dict], top_n: int = 3) -> list[str]:
    """Return IDs of top-cited papers."""
    sorted_nodes = sorted(
        nodes,
        key=lambda n: n.get("citation_count", 0) or 0,
        reverse=True,
    )
    return [n["id"] for n in sorted_nodes[:top_n]]


def _identify_bridge_papers(
    nodes: list[dict],
    edges: list[dict],
    paper_cluster_map: dict[str, str],
) -> list[str]:
    """Find papers that connect different clusters via citations."""
    bridge_ids: list[str] = []
    for node in nodes:
        pid = node["id"]
        my_cluster = paper_cluster_map.get(pid)
        if not my_cluster:
            continue

        # Check if this paper has edges to papers in other clusters
        connected_clusters: set[str] = set()
        for edge in edges:
            if edge["source"] == pid:
                target_cluster = paper_cluster_map.get(edge["target"])
                if target_cluster and target_cluster != my_cluster:
                    connected_clusters.add(target_cluster)
            elif edge["target"] == pid:
                source_cluster = paper_cluster_map.get(edge["source"])
                if source_cluster and source_cluster != my_cluster:
                    connected_clusters.add(source_cluster)

        if connected_clusters:
            bridge_ids.append(pid)

    return bridge_ids


# ── 4. Timeline ──


def build_yearly_data(analyses: list[dict]) -> list[dict]:
    """Build year-based paper grouping (algorithmic)."""
    by_year: dict[int, list[dict]] = defaultdict(list)
    for a in analyses:
        year = a.get("year")
        if year:
            by_year[year].append(a)

    yearly = []
    for year in sorted(by_year.keys()):
        papers = by_year[year]
        yearly.append({
            "year": year,
            "papers": papers,
            "paper_count": len(papers),
            "paper_ids": [
                p.get("paper_id") or p.get("s2_id") or p.get("title", "")[:50]
                for p in papers
            ],
        })
    return yearly


async def build_timeline(
    analyses: list[dict],
    user_query: str,
    llm: LLMRouter,
    prompt_manager: PromptManager,
    token_usage: dict | None = None,
) -> tuple[list[dict], dict]:
    """Build timeline with LLM milestone identification.

    Returns:
        (timeline_list, updated_token_usage)
    """
    yearly_data = build_yearly_data(analyses)

    if not yearly_data:
        return [], token_usage or {}

    prompt = prompt_manager.render(
        "analyst",
        "timeline_milestones",
        user_query=user_query,
        yearly_papers=yearly_data,
    )

    response_text, token_usage = await llm.call(
        prompt=prompt,
        agent_name="analyst",
        task_type="topic_clustering",  # reuse routing
        token_usage=token_usage,
    )

    parsed = _parse_json_response(response_text)

    # Merge LLM milestones with algorithmic yearly data
    milestone_map: dict[int, dict] = {}
    if parsed and "milestones" in parsed:
        for m in parsed["milestones"]:
            year = m.get("year")
            if year:
                milestone_map[year] = m

    timeline = []
    for entry in yearly_data:
        year = entry["year"]
        milestone_info = milestone_map.get(year, {})
        timeline.append({
            "year": year,
            "milestone": milestone_info.get("milestone"),
            "paper_ids": entry["paper_ids"],
            "paper_count": entry["paper_count"],
            "key_event": milestone_info.get("key_event"),
        })

    logger.info("analyst.timeline_built", years=len(timeline))
    return timeline, token_usage


# ── 5. Research Trends ──


def compute_trend_stats(
    analyses: list[dict],
    topic_clusters: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Compute year and topic statistics (algorithmic).

    Returns:
        (by_year_stats, by_topic_stats)
    """
    # By year
    by_year: dict[int, dict] = defaultdict(lambda: {"count": 0, "citations_sum": 0})
    for a in analyses:
        year = a.get("year")
        if year:
            by_year[year]["count"] += 1
            by_year[year]["citations_sum"] += a.get("citation_count", 0) or 0

    by_year_stats = [
        {"year": y, "count": d["count"], "citations_sum": d["citations_sum"]}
        for y, d in sorted(by_year.items())
    ]

    # By topic (from clusters)
    by_topic_stats = []
    for cluster in topic_clusters:
        # Build yearly counts for this cluster
        cluster_paper_ids = set(cluster.get("paper_ids", []))
        yearly_counts: dict[int, int] = defaultdict(int)
        for a in analyses:
            pid = a.get("paper_id") or a.get("s2_id") or a.get("title", "")[:50]
            if pid in cluster_paper_ids and a.get("year"):
                yearly_counts[a["year"]] += 1

        by_topic_stats.append({
            "name": cluster.get("name", ""),
            "paper_count": cluster.get("paper_count", 0),
            "yearly_counts": [
                {"year": y, "count": c} for y, c in sorted(yearly_counts.items())
            ],
            "key_terms": cluster.get("key_terms", []),
        })

    return by_year_stats, by_topic_stats


async def analyze_trends(
    analyses: list[dict],
    topic_clusters: list[dict],
    user_query: str,
    llm: LLMRouter,
    prompt_manager: PromptManager,
    token_usage: dict | None = None,
) -> tuple[dict, dict]:
    """Analyze research trends: algorithmic stats + LLM interpretation.

    Returns:
        (research_trends_dict, updated_token_usage)
    """
    by_year_stats, by_topic_stats = compute_trend_stats(analyses, topic_clusters)

    prompt = prompt_manager.render(
        "analyst",
        "trend_analysis",
        user_query=user_query,
        by_year=by_year_stats,
        by_topic=by_topic_stats,
    )

    response_text, token_usage = await llm.call(
        prompt=prompt,
        agent_name="analyst",
        task_type="comparison",  # reuse routing
        token_usage=token_usage,
    )

    parsed = _parse_json_response(response_text)

    # Merge LLM trends into topic stats
    if parsed and "topic_trends" in parsed:
        trend_map = {t["topic"]: t["trend"] for t in parsed["topic_trends"]}
    else:
        trend_map = {}

    by_topic_with_trends = []
    for ts in by_topic_stats:
        by_topic_with_trends.append({
            "topic": ts["name"],
            "trend": trend_map.get(ts["name"], "stable"),
            "yearly_counts": ts["yearly_counts"],
        })

    trends = {
        "by_year": by_year_stats,
        "by_topic": by_topic_with_trends,
        "emerging_topics": parsed.get("emerging_topics", []) if parsed else [],
        "narrative": parsed.get("narrative", "") if parsed else "",
    }

    logger.info("analyst.trends_analyzed", topics=len(by_topic_with_trends))
    return trends, token_usage


# ── Analyst Agent Node ──


async def analyze_node(
    state: ReviewState,
    llm: LLMRouter | None = None,
    prompt_manager: PromptManager | None = None,
) -> dict:
    """Analyst Agent node function.

    Inputs from state:
        - paper_analyses: list of paper analysis dicts from Reader
        - user_query: original research question

    Returns:
        Partial state with topic_clusters, comparison_matrix,
        citation_network, timeline, research_trends, token_usage,
        current_phase.
    """
    llm = llm or LLMRouter()
    prompt_manager = prompt_manager or PromptManager()

    analyses = state.get("paper_analyses", [])
    user_query = state.get("user_query", "")
    token_usage = state.get("token_usage")

    # Threshold check: skip if too few papers
    if len(analyses) < MIN_PAPERS_FOR_ANALYSIS:
        logger.info(
            "analyst.skipped",
            reason="insufficient_papers",
            count=len(analyses),
            threshold=MIN_PAPERS_FOR_ANALYSIS,
        )
        return {
            "topic_clusters": [],
            "comparison_matrix": {"title": "方法对比矩阵", "dimensions": [], "methods": [], "narrative": ""},
            "citation_network": {"nodes": [], "edges": [], "key_papers": [], "bridge_papers": []},
            "timeline": [],
            "research_trends": {"by_year": [], "by_topic": [], "emerging_topics": [], "narrative": ""},
            "current_phase": "critiquing",
            "token_usage": token_usage,
        }

    # Cap at MAX_PAPERS_FOR_ANALYSIS
    working_analyses = analyses
    if len(analyses) > MAX_PAPERS_FOR_ANALYSIS:
        logger.warning(
            "analyst.capped",
            original=len(analyses),
            capped=MAX_PAPERS_FOR_ANALYSIS,
        )
        # Sort by citation count descending, keep top N
        working_analyses = sorted(
            analyses,
            key=lambda a: a.get("citation_count", 0) or 0,
            reverse=True,
        )[:MAX_PAPERS_FOR_ANALYSIS]

    # 1. Topic clustering
    topic_clusters, token_usage = await build_topic_clusters(
        working_analyses, user_query, llm, prompt_manager, token_usage
    )

    # 2. Comparison matrix
    comparison_matrix, token_usage = await build_comparison_matrix(
        working_analyses, user_query, llm, prompt_manager, token_usage
    )

    # 3. Citation network (algorithmic, no LLM)
    citation_network = build_citation_network(working_analyses, topic_clusters)

    # 4. Timeline
    timeline, token_usage = await build_timeline(
        working_analyses, user_query, llm, prompt_manager, token_usage
    )

    # 5. Research trends
    research_trends, token_usage = await analyze_trends(
        working_analyses, topic_clusters, user_query, llm, prompt_manager, token_usage
    )

    logger.info(
        "agent.analyze_complete",
        papers=len(working_analyses),
        clusters=len(topic_clusters),
    )

    return {
        "topic_clusters": topic_clusters,
        "comparison_matrix": comparison_matrix,
        "citation_network": citation_network,
        "timeline": timeline,
        "research_trends": research_trends,
        "token_usage": token_usage,
        "current_phase": "critiquing",
    }


agent_registry.register("analyze", analyze_node)
