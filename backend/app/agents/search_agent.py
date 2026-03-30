"""Search Agent — multi-source literature search with dedup + snowball + ranking.

Components (aligned with §5.1):
  - Query Planner: natural language → structured queries (done by parse_intent)
  - Multi-Source Fetcher: parallel search via SourceRegistry
  - Deduplicator: DOI / S2 ID / arXiv ID / title similarity
  - Snowball Crawler: citation chain expansion (depth 2, single 50, total 200)
  - Ranker: relevance + citation count + recency scoring
"""

import asyncio
import json
from typing import Any

import structlog

from app.agents.registry import agent_registry
from app.agents.state import ReviewState
from app.schemas.paper import PaperMetadata
from app.services.llm import LLMRouter
from app.services.prompt_manager import PromptManager
from app.sources.registry import SourceRegistry

logger = structlog.stdlib.get_logger()

# ── Snowball crawling constraints ──
MAX_SNOWBALL_DEPTH = 2
SINGLE_HOP_LIMIT = 50
TOTAL_CANDIDATE_LIMIT = 200


# ── Multi-Source Fetch ──


async def multi_source_fetch(
    registry: SourceRegistry, query: str, filters: dict | None = None
) -> list[PaperMetadata]:
    """Search all enabled data sources in parallel."""
    sources = registry.get_enabled_sources()
    if not sources:
        logger.warning("search.no_enabled_sources")
        return []

    tasks = [source.search(query, filters) for _, source in sources]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_papers: list[PaperMetadata] = []
    for (name, _), result in zip(sources, results):
        if isinstance(result, Exception):
            logger.warning("source.search_failed", source=name, error=str(result))
            continue
        all_papers.extend(result)

    logger.info(
        "search.multi_source_complete",
        sources=len(sources),
        total_results=len(all_papers),
    )
    return all_papers


# ── Deduplication ──


def _paper_key(p: PaperMetadata | dict) -> str:
    """Generate a dedup key from a paper's external IDs."""
    if isinstance(p, dict):
        doi = p.get("doi")
        s2 = p.get("s2_id")
        arxiv = p.get("arxiv_id")
        title = p.get("title", "")
    else:
        doi = p.doi
        s2 = p.s2_id
        arxiv = p.arxiv_id
        title = p.title

    if doi:
        return f"doi:{doi.lower()}"
    if s2:
        return f"s2:{s2}"
    if arxiv:
        return f"arxiv:{arxiv}"
    return f"title:{title.lower().strip()[:80]}"


def deduplicate_papers(
    papers: list[PaperMetadata],
) -> list[PaperMetadata]:
    """Remove duplicate papers by DOI > S2 ID > arXiv ID > title."""
    seen: dict[str, int] = {}
    unique: list[PaperMetadata] = []

    for paper in papers:
        key = _paper_key(paper)
        if key not in seen:
            seen[key] = len(unique)
            unique.append(paper)
        else:
            # Merge: keep the one with more info
            existing = unique[seen[key]]
            if (paper.citation_count or 0) > (existing.citation_count or 0):
                unique[seen[key]] = paper

    logger.info(
        "search.dedup",
        before=len(papers),
        after=len(unique),
        removed=len(papers) - len(unique),
    )
    return unique


# ── Snowball Crawler ──


async def snowball_crawl(
    registry: SourceRegistry,
    seed_papers: list[PaperMetadata],
    existing_keys: set[str],
    max_depth: int = MAX_SNOWBALL_DEPTH,
    single_hop_limit: int = SINGLE_HOP_LIMIT,
    total_limit: int = TOTAL_CANDIDATE_LIMIT,
) -> list[PaperMetadata]:
    """Expand from seed papers by following citation/reference links.

    Args:
        registry: Source registry for fetching citations/references.
        seed_papers: Papers to start from.
        existing_keys: Set of already-seen paper dedup keys.
        max_depth: Maximum recursion depth (default 2).
        single_hop_limit: Max papers per hop (default 50).
        total_limit: Global candidate cap.

    Returns:
        List of newly discovered papers (not in existing_keys).
    """
    discovered: list[PaperMetadata] = []
    seen = set(existing_keys)

    # Use Semantic Scholar for snowballing (it supports citations/references)
    s2_source = registry.get_source("semantic_scholar")
    if not s2_source:
        return discovered

    current_layer = seed_papers[:20]  # limit seeds to avoid explosion

    for depth in range(max_depth):
        if len(discovered) >= total_limit:
            break

        next_layer: list[PaperMetadata] = []
        hop_count = 0

        for paper in current_layer:
            if hop_count >= single_hop_limit:
                break

            paper_id = paper.s2_id if hasattr(paper, "s2_id") else (paper.get("s2_id") if isinstance(paper, dict) else None)
            if not paper_id:
                continue

            try:
                refs = await s2_source.get_references(paper_id)
                cits = await s2_source.get_citations(paper_id)
                related = refs + cits
            except Exception as exc:
                logger.debug("snowball.fetch_failed", paper_id=paper_id, error=str(exc))
                continue

            for p in related:
                key = _paper_key(p)
                if key not in seen:
                    seen.add(key)
                    discovered.append(p)
                    next_layer.append(p)
                    hop_count += 1
                    if hop_count >= single_hop_limit or len(discovered) >= total_limit:
                        break

        current_layer = next_layer
        if not current_layer:
            break

    logger.info(
        "search.snowball",
        depth=min(depth + 1, max_depth) if seed_papers else 0,
        discovered=len(discovered),
    )
    return discovered[:total_limit]


# ── Ranker ──


def rank_papers(
    papers: list[PaperMetadata],
    key_concepts: list[str] | None = None,
) -> list[PaperMetadata]:
    """Rank papers by a composite score: relevance + citations + recency.

    Simple heuristic ranker (no LLM call). Factors:
    - Citation count (log-scaled)
    - Recency (newer papers score higher)
    - Title/abstract keyword match against key concepts
    """
    import math

    current_year = 2026  # fixed for deterministic scoring
    concepts_lower = [c.lower() for c in (key_concepts or [])]

    def score(p: PaperMetadata) -> float:
        # Citation score: log2(1 + citations), capped at 20
        cit_score = min(math.log2(1 + (p.citation_count or 0)), 20) / 20

        # Recency score: papers from recent 5 years score higher
        year = p.year or 2020
        recency = max(0, min(1, (year - (current_year - 10)) / 10))

        # Keyword relevance: fraction of key concepts found in title+abstract
        text = f"{p.title} {p.abstract or ''}".lower()
        if concepts_lower:
            keyword_hits = sum(1 for c in concepts_lower if c in text)
            keyword_score = keyword_hits / len(concepts_lower)
        else:
            keyword_score = 0.5

        return keyword_score * 0.5 + cit_score * 0.3 + recency * 0.2

    ranked = sorted(papers, key=score, reverse=True)
    return ranked


# ── Search Agent Node ──


async def search_node(
    state: ReviewState,
    source_registry: SourceRegistry | None = None,
    llm: LLMRouter | None = None,
    prompt_manager: PromptManager | None = None,
) -> dict:
    """Search Agent node function: multi-source fetch → dedup → snowball → rank.

    Inputs from state:
        - search_strategy: contains queries and filters
        - feedback_search_queries: additional queries from feedback loop

    Returns:
        Partial state update with ``candidate_papers`` and ``current_phase``.
    """
    from app.sources import create_source_registry
    from app.config import settings

    source_registry = source_registry or create_source_registry(settings)

    strategy = state.get("search_strategy", {})
    queries = strategy.get("queries", [])
    filters = strategy.get("suggested_filters", {})
    key_concepts = strategy.get("key_concepts", [])

    # Include feedback queries if present (feedback loop)
    feedback_queries = state.get("feedback_search_queries", [])
    if feedback_queries:
        for fq in feedback_queries:
            queries.append({"query": fq, "purpose": "feedback supplement"})

    if not queries:
        queries = [{"query": state.get("user_query", ""), "purpose": "direct query"}]

    # 1. Multi-source fetch for each query
    all_papers: list[PaperMetadata] = []
    for q_entry in queries:
        query_text = q_entry["query"] if isinstance(q_entry, dict) else str(q_entry)
        results = await multi_source_fetch(source_registry, query_text, filters)
        all_papers.extend(results)

    # 2. Deduplicate
    unique_papers = deduplicate_papers(all_papers)

    # 3. Snowball crawling from top-ranked seeds
    existing_keys = {_paper_key(p) for p in unique_papers}
    if len(unique_papers) > 0:
        # Use top 10 papers as seeds
        seeds = unique_papers[:10]
        snowball_results = await snowball_crawl(
            source_registry, seeds, existing_keys
        )
        unique_papers.extend(snowball_results)
        unique_papers = deduplicate_papers(unique_papers)

    # 4. Enforce total limit
    unique_papers = unique_papers[:TOTAL_CANDIDATE_LIMIT]

    # 5. Rank
    ranked = rank_papers(unique_papers, key_concepts)

    # Convert to dicts for state serialization
    candidate_papers = [p.model_dump() for p in ranked]

    logger.info(
        "agent.search_complete",
        total_candidates=len(candidate_papers),
        queries_used=len(queries),
    )

    return {
        "candidate_papers": candidate_papers,
        "current_phase": "search_review",
        "token_usage": state.get("token_usage"),
        "feedback_search_queries": [],  # clear feedback after processing
    }


agent_registry.register("search", search_node)
