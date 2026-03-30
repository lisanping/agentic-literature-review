"""Reader Agent — PDF processing, info extraction, relation detection.

Components (aligned with §5.2):
  - PDF Processor: download PDF → parse with PyMuPDF → structured text
  - Abstract Analyzer: fallback when full text is unavailable
  - Info Extractor: LLM structured extraction of paper components
  - Relation Detector: identify inter-paper academic relationships
  - Parallel Processing: asyncio.Semaphore(5) with progressive SSE push
"""

import asyncio
import json
from pathlib import Path

import httpx
import structlog

from app.agents.registry import agent_registry
from app.agents.state import ReviewState
from app.parsers.pdf_parser import parse_pdf
from app.services.llm import LLMRouter
from app.services.prompt_manager import PromptManager

logger = structlog.stdlib.get_logger()

MAX_CONCURRENT = 5


# ── PDF download ──


async def download_pdf(pdf_url: str, dest_dir: str = "data/pdfs") -> str | None:
    """Download a PDF file and return the local path, or None on failure."""
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    import hashlib

    filename = hashlib.sha256(pdf_url.encode()).hexdigest()[:16] + ".pdf"
    filepath = dest / filename

    if filepath.exists():
        return str(filepath)

    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(pdf_url)
            if resp.status_code == 200 and len(resp.content) > 1000:
                filepath.write_bytes(resp.content)
                return str(filepath)
    except Exception as exc:
        logger.debug("reader.pdf_download_failed", url=pdf_url, error=str(exc))
    return None


# ── Info Extraction ──


async def extract_paper_info(
    paper: dict,
    content: str,
    user_query: str,
    llm: LLMRouter,
    prompt_manager: PromptManager,
) -> dict:
    """Use LLM to extract structured information from paper content.

    Returns a dict with: objective, methodology, datasets, findings,
    limitations, key_concepts, method_category.
    """
    prompt = prompt_manager.render(
        "reader",
        "info_extraction",
        title=paper.get("title", ""),
        authors=", ".join(paper.get("authors", [])),
        year=paper.get("year", ""),
        content=content[:8000],  # limit context to avoid token overflow
        user_query=user_query,
    )

    response_text, token_usage = await llm.call(
        prompt=prompt,
        agent_name="reader",
        task_type="info_extraction",
        token_usage=None,
    )

    return _parse_extraction_response(response_text), token_usage


def _parse_extraction_response(response_text: str) -> dict:
    """Parse LLM info extraction response into a structured dict."""
    try:
        text = response_text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        result = json.loads(text)
        return {
            "objective": result.get("objective"),
            "methodology": result.get("methodology") or result.get("method"),
            "datasets": result.get("datasets", result.get("dataset", [])),
            "findings": result.get("findings"),
            "limitations": result.get("limitations"),
            "key_concepts": result.get("key_concepts", []),
            "method_category": result.get("method_category"),
        }
    except (json.JSONDecodeError, IndexError):
        logger.warning("reader.extraction_parse_failed")
        return {
            "objective": None,
            "methodology": None,
            "datasets": [],
            "findings": None,
            "limitations": None,
            "key_concepts": [],
            "method_category": None,
        }


# ── Process a single paper ──


async def process_single_paper(
    paper: dict,
    user_query: str,
    llm: LLMRouter,
    prompt_manager: PromptManager,
) -> dict:
    """Process a single paper: download PDF → parse → extract info.

    Falls back to abstract-only analysis if PDF is unavailable or fails.

    Returns:
        Analysis dict with paper_id, extracted info, and analysis_depth.
    """
    paper_id = paper.get("s2_id") or paper.get("doi") or paper.get("arxiv_id") or paper.get("title", "")[:50]
    analysis_depth = "abstract_only"
    content = paper.get("abstract", "") or ""

    # Try full-text extraction if PDF is available
    pdf_url = paper.get("pdf_url")
    if pdf_url and paper.get("open_access", False):
        pdf_path = await download_pdf(pdf_url)
        if pdf_path:
            parsed = parse_pdf(pdf_path)
            if parsed.success and len(parsed.text) > 200:
                content = parsed.text
                analysis_depth = "fulltext"
                logger.debug("reader.fulltext", paper_id=paper_id, chars=len(content))

    if not content:
        content = f"Title: {paper.get('title', '')}. No content available."

    # LLM extraction
    extraction, token_usage = await extract_paper_info(
        paper, content, user_query, llm, prompt_manager
    )

    return {
        "paper_id": paper_id,
        "title": paper.get("title", ""),
        "analysis_depth": analysis_depth,
        "token_usage_delta": token_usage,
        **extraction,
    }


# ── Parallel reader ──


async def read_papers_parallel(
    papers: list[dict],
    user_query: str,
    llm: LLMRouter,
    prompt_manager: PromptManager,
    max_concurrent: int = MAX_CONCURRENT,
) -> tuple[list[dict], dict]:
    """Read multiple papers in parallel with concurrency control.

    Returns:
        (analyses_list, aggregated_token_usage)
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results: list[dict] = []
    total = len(papers)
    completed = 0
    aggregated_usage: dict = {}

    async def _process(paper: dict) -> dict | None:
        nonlocal completed
        async with semaphore:
            try:
                analysis = await process_single_paper(
                    paper, user_query, llm, prompt_manager
                )
                completed += 1
                logger.info(
                    "reader.progress",
                    completed=completed,
                    total=total,
                    paper=paper.get("title", "")[:60],
                )
                return analysis
            except Exception as exc:
                completed += 1
                logger.warning(
                    "reader.paper_failed",
                    paper=paper.get("title", "")[:60],
                    error=str(exc),
                )
                return {
                    "paper_id": paper.get("s2_id") or paper.get("title", "")[:50],
                    "title": paper.get("title", ""),
                    "analysis_depth": "failed",
                    "objective": None,
                    "methodology": None,
                    "datasets": [],
                    "findings": None,
                    "limitations": None,
                    "key_concepts": [],
                    "method_category": None,
                }

    analyses = await asyncio.gather(
        *[_process(p) for p in papers], return_exceptions=False
    )

    # Collect results and aggregate token usage
    from app.services.llm import update_token_usage

    for analysis in analyses:
        if analysis:
            results.append(analysis)
            delta = analysis.pop("token_usage_delta", None)
            if delta:
                aggregated_usage = delta  # LLM already aggregates

    return results, aggregated_usage


# ── Reader Agent Node ──


async def read_node(
    state: ReviewState,
    llm: LLMRouter | None = None,
    prompt_manager: PromptManager | None = None,
) -> dict:
    """Reader Agent node function.

    Inputs from state:
        - selected_papers: user-confirmed paper list
        - user_query: original research question

    Returns:
        Partial state with ``paper_analyses``, ``reading_progress``,
        ``fulltext_coverage``, ``token_usage``.
    """
    llm = llm or LLMRouter()
    prompt_manager = prompt_manager or PromptManager()

    papers = state.get("selected_papers", [])
    user_query = state.get("user_query", "")

    if not papers:
        return {
            "paper_analyses": [],
            "current_phase": "outlining",
            "reading_progress": {"total": 0, "completed": 0},
        }

    analyses, token_usage = await read_papers_parallel(
        papers, user_query, llm, prompt_manager
    )

    # Compute fulltext coverage
    fulltext_count = sum(1 for a in analyses if a.get("analysis_depth") == "fulltext")
    abstract_count = sum(1 for a in analyses if a.get("analysis_depth") == "abstract_only")

    # Check if Reader discovered papers needing additional search
    feedback_queries: list[str] = []
    # (In a full implementation, the LLM would suggest additional queries
    #  based on frequently-cited but uncollected references)

    logger.info(
        "agent.read_complete",
        total=len(analyses),
        fulltext=fulltext_count,
        abstract_only=abstract_count,
    )

    return {
        "paper_analyses": analyses,
        "reading_progress": {
            "total": len(papers),
            "completed": len(analyses),
        },
        "fulltext_coverage": {
            "total": len(analyses),
            "fulltext_count": fulltext_count,
            "abstract_only_count": abstract_count,
        },
        "feedback_search_queries": feedback_queries,
        "token_usage": token_usage or state.get("token_usage"),
        "current_phase": "outlining",
    }


agent_registry.register("read", read_node)
