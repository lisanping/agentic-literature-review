"""Update Agent — new literature monitoring and incremental update reports.

Workflow:
  1. Load original search_strategy + existing paper set
  2. Incremental search with date_range filter (since last_search_at)
  3. Diff: new papers vs existing papers (dedup)
  4. Relevance assessment: LLM batch scoring
  5. Read new high-relevance papers (reuse Reader logic)
  6. Generate update report: LLM summarizes new findings + impact assessment
  7. Persist: new papers → project_papers, report → review_outputs
"""

import asyncio
import json
from datetime import datetime, timezone

import structlog

from app.agents.registry import agent_registry
from app.agents.state import ReviewState
from app.services.llm import LLMRouter
from app.services.prompt_manager import PromptManager
from app.sources.registry import SourceRegistry

logger = structlog.stdlib.get_logger()

RELEVANCE_THRESHOLD = 6  # Papers with score >= 6 are considered relevant
MAX_NEW_PAPERS_FOR_READING = 30


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
        logger.warning("update.json_parse_failed", preview=text[:200])
        return None


# ── 1. Incremental Search ──


async def incremental_search(
    state: ReviewState,
    source_registry: SourceRegistry | None = None,
) -> list[dict]:
    """Search for new papers published since last_search_at."""
    from app.config import settings
    from app.sources import create_source_registry

    registry = source_registry or create_source_registry(settings)
    strategy = state.get("search_strategy", {})
    queries = strategy.get("queries", [])
    last_search = state.get("last_search_at")

    if not queries:
        # Fallback: use the original user query
        user_query = state.get("user_query", "")
        if user_query:
            queries = [user_query]

    # Build date filter
    filters: dict = {}
    if last_search:
        try:
            dt = datetime.fromisoformat(last_search)
            filters["year_range"] = {"min": dt.year}
        except (ValueError, TypeError):
            pass

    filters["max_papers"] = 50

    all_papers: list[dict] = []
    enabled_sources = registry.get_enabled_sources()

    for query in queries[:3]:  # Limit to first 3 queries
        tasks = []
        for name, source in enabled_sources:
            tasks.append(_search_one_source(name, source, query, filters))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.warning("update.search_error", error=str(result))
                continue
            all_papers.extend(result)

    logger.info("update.incremental_search", total_found=len(all_papers))
    return all_papers


async def _search_one_source(
    name: str, source, query: str, filters: dict
) -> list[dict]:
    """Search a single source, return paper dicts."""
    try:
        results = await source.search(query, filters)
        return [r.model_dump() for r in results]
    except Exception as e:
        logger.warning("update.source_search_failed", source=name, error=str(e))
        return []


# ── 2. Diff: Filter Out Already-Known Papers ──


def diff_papers(
    new_papers: list[dict],
    existing_papers: list[dict],
) -> list[dict]:
    """Remove papers already present in the existing set.

    Uses DOI > S2 ID > arXiv ID > OpenAlex ID > PMID > title matching.
    """
    existing_ids: set[str] = set()
    existing_titles: set[str] = set()

    for p in existing_papers:
        if p.get("doi"):
            existing_ids.add(f"doi:{p['doi']}")
        if p.get("s2_id"):
            existing_ids.add(f"s2:{p['s2_id']}")
        if p.get("arxiv_id"):
            existing_ids.add(f"arxiv:{p['arxiv_id']}")
        if p.get("openalex_id"):
            existing_ids.add(f"oa:{p['openalex_id']}")
        if p.get("pmid"):
            existing_ids.add(f"pmid:{p['pmid']}")
        if p.get("title"):
            existing_titles.add(p["title"].lower().strip())

    truly_new: list[dict] = []
    seen: set[str] = set()

    for p in new_papers:
        # Check ID-based dedup
        matched = False
        for key_prefix, field in [
            ("doi", "doi"),
            ("s2", "s2_id"),
            ("arxiv", "arxiv_id"),
            ("oa", "openalex_id"),
            ("pmid", "pmid"),
        ]:
            val = p.get(field)
            if val and f"{key_prefix}:{val}" in existing_ids:
                matched = True
                break

        if matched:
            continue

        # Check title-based dedup
        title = (p.get("title") or "").lower().strip()
        if title and title in existing_titles:
            continue

        # Dedup within new papers
        dedup_key = p.get("doi") or p.get("s2_id") or p.get("arxiv_id") or title
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        truly_new.append(p)

    logger.info(
        "update.diff",
        new_total=len(new_papers),
        existing_count=len(existing_papers),
        truly_new=len(truly_new),
    )
    return truly_new


# ── 3. Relevance Assessment ──


async def assess_relevance(
    papers: list[dict],
    user_query: str,
    llm: LLMRouter | None = None,
    prompt_manager: PromptManager | None = None,
) -> list[dict]:
    """Use LLM to batch-score new papers for relevance.

    Returns papers with score >= RELEVANCE_THRESHOLD, sorted by score desc.
    """
    if not papers:
        return []

    from app.config import settings

    llm = llm or LLMRouter(settings)
    prompt_manager = prompt_manager or PromptManager(settings.PROMPTS_DIR)

    # Process in batches of 15 to avoid token limits
    batch_size = 15
    scored_papers: list[tuple[dict, float, str]] = []

    for i in range(0, len(papers), batch_size):
        batch = papers[i : i + batch_size]
        prompt = prompt_manager.render(
            "update/relevance_filter",
            user_query=user_query,
            papers=batch,
        )

        response_text = await llm.call(
            prompt=prompt,
            agent_name="update",
            task_type="relevance_filter",
        )

        parsed = _parse_json_response(response_text)
        if not isinstance(parsed, list):
            # If parsing fails, include all papers with default score
            for paper in batch:
                scored_papers.append((paper, 5.0, "parse_failed"))
            continue

        for item in parsed:
            idx = item.get("index", 0) - 1
            score = float(item.get("score", 0))
            reason = item.get("reason", "")
            if 0 <= idx < len(batch):
                scored_papers.append((batch[idx], score, reason))

    # Filter by threshold and sort
    relevant = [
        {**paper, "_relevance_score": score, "_relevance_reason": reason}
        for paper, score, reason in scored_papers
        if score >= RELEVANCE_THRESHOLD
    ]
    relevant.sort(key=lambda x: x.get("_relevance_score", 0), reverse=True)

    logger.info(
        "update.relevance_assessment",
        total=len(papers),
        relevant=len(relevant),
        threshold=RELEVANCE_THRESHOLD,
    )
    return relevant[:MAX_NEW_PAPERS_FOR_READING]


# ── 4. Generate Update Report ──


async def generate_update_report(
    user_query: str,
    existing_count: int,
    new_analyses: list[dict],
    llm: LLMRouter | None = None,
    prompt_manager: PromptManager | None = None,
) -> str:
    """Generate an incremental update report using LLM."""
    if not new_analyses:
        return "本次更新检查未发现新的高相关论文。综述内容无需修订。"

    from app.config import settings

    llm = llm or LLMRouter(settings)
    prompt_manager = prompt_manager or PromptManager(settings.PROMPTS_DIR)

    prompt = prompt_manager.render(
        "update/update_report",
        user_query=user_query,
        existing_count=existing_count,
        new_count=len(new_analyses),
        new_analyses=new_analyses,
    )

    report = await llm.call(
        prompt=prompt,
        agent_name="update",
        task_type="update_report",
    )

    logger.info("update.report_generated", report_length=len(report))
    return report


# ── 5. Node Function ──


async def update_node(
    state: ReviewState,
    *,
    source_registry: SourceRegistry | None = None,
    llm: LLMRouter | None = None,
    prompt_manager: PromptManager | None = None,
) -> dict:
    """Update Agent node — check for new papers and generate update report.

    Input (from state):
        - project_id, user_query, search_strategy
        - selected_papers: existing papers (for dedup)
        - last_search_at: ISO timestamp of last search

    Output:
        - new_papers_found: list of newly discovered paper dicts
        - update_report: incremental update report text
        - last_search_at: updated to current time
        - current_phase: "updating"
    """
    project_id = state.get("project_id", "")
    user_query = state.get("user_query", "")
    existing_papers = state.get("selected_papers") or state.get("candidate_papers") or []

    logger.info(
        "update.start",
        project_id=project_id,
        existing_count=len(existing_papers),
    )

    if not user_query:
        logger.warning("update.no_user_query", project_id=project_id)
        return {
            "new_papers_found": [],
            "update_report": "无法执行更新：缺少原始研究问题。",
            "current_phase": "updating",
        }

    # Step 1: Incremental search
    raw_new = await incremental_search(state, source_registry)

    # Step 2: Diff with existing papers
    truly_new = diff_papers(raw_new, existing_papers)

    if not truly_new:
        now = datetime.now(timezone.utc).isoformat()
        return {
            "new_papers_found": [],
            "update_report": "本次更新检查未发现新论文。综述内容保持最新。",
            "last_search_at": now,
            "current_phase": "updating",
        }

    # Step 3: Relevance assessment
    relevant = await assess_relevance(truly_new, user_query, llm, prompt_manager)

    if not relevant:
        now = datetime.now(timezone.utc).isoformat()
        return {
            "new_papers_found": [],
            "update_report": "本次检查发现了一些新论文，但无高相关论文。综述内容无需修订。",
            "last_search_at": now,
            "current_phase": "updating",
        }

    # Step 4: Build analysis summaries for report generation
    # Use available metadata as "analyses" (full Reader integration is optional)
    new_analyses = []
    for p in relevant:
        new_analyses.append({
            "title": p.get("title", ""),
            "year": p.get("year"),
            "findings": p.get("abstract", "")[:300] if p.get("abstract") else "未提取",
            "methodology": "未提取",
            "limitations": "未提取",
        })

    # Step 5: Generate update report
    report = await generate_update_report(
        user_query=user_query,
        existing_count=len(existing_papers),
        new_analyses=new_analyses,
        llm=llm,
        prompt_manager=prompt_manager,
    )

    # Clean papers for state storage (remove internal scoring fields)
    clean_papers = []
    for p in relevant:
        clean = {k: v for k, v in p.items() if not k.startswith("_")}
        clean_papers.append(clean)

    now = datetime.now(timezone.utc).isoformat()
    logger.info(
        "update.complete",
        project_id=project_id,
        new_papers=len(clean_papers),
        report_length=len(report),
    )

    return {
        "new_papers_found": clean_papers,
        "update_report": report,
        "last_search_at": now,
        "current_phase": "updating",
    }


agent_registry.register("update", update_node)
