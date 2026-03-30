"""arXiv data source adapter.

API docs: https://info.arxiv.org/help/api/basics.html
Rate limit: 3 requests per second.
Uses the arXiv Atom XML API.
"""

import re
import xml.etree.ElementTree as ET

import httpx
import structlog

from app.schemas.paper import PaperMetadata
from app.sources.base import PaperSource
from app.sources.rate_limiter import RateLimiter

logger = structlog.stdlib.get_logger()

ARXIV_API_BASE = "http://export.arxiv.org/api/query"
ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"

# Extract arXiv ID from URL like http://arxiv.org/abs/2301.00001v2
_ARXIV_ID_RE = re.compile(r"arxiv\.org/abs/([^\s?#]+)")


def _extract_arxiv_id(entry: ET.Element) -> str | None:
    """Extract the arXiv ID from an entry's <id> tag."""
    id_el = entry.find(f"{ATOM_NS}id")
    if id_el is None or not id_el.text:
        return None
    match = _ARXIV_ID_RE.search(id_el.text)
    if match:
        # Strip version suffix (e.g., "v2")
        raw_id = match.group(1)
        return re.sub(r"v\d+$", "", raw_id)
    return None


def _parse_entry(entry: ET.Element) -> PaperMetadata | None:
    """Parse an arXiv Atom <entry> into PaperMetadata."""
    title_el = entry.find(f"{ATOM_NS}title")
    if title_el is None or not title_el.text:
        return None
    title = " ".join(title_el.text.split())  # collapse whitespace

    # Authors
    authors = []
    for author_el in entry.findall(f"{ATOM_NS}author"):
        name_el = author_el.find(f"{ATOM_NS}name")
        if name_el is not None and name_el.text:
            authors.append(name_el.text.strip())

    # Abstract
    summary_el = entry.find(f"{ATOM_NS}summary")
    abstract = " ".join(summary_el.text.split()) if summary_el is not None and summary_el.text else None

    # Year from <published>
    published_el = entry.find(f"{ATOM_NS}published")
    year = None
    if published_el is not None and published_el.text:
        year = int(published_el.text[:4])

    # arXiv ID
    arxiv_id = _extract_arxiv_id(entry)

    # DOI (if present)
    doi_el = entry.find(f"{ARXIV_NS}doi")
    doi = doi_el.text.strip() if doi_el is not None and doi_el.text else None

    # PDF link
    pdf_url = None
    for link_el in entry.findall(f"{ATOM_NS}link"):
        if link_el.get("title") == "pdf":
            pdf_url = link_el.get("href")
            break

    # Source URL (abstract page)
    source_url = None
    id_el = entry.find(f"{ATOM_NS}id")
    if id_el is not None and id_el.text:
        source_url = id_el.text.strip()

    # Primary category
    category_el = entry.find(f"{ARXIV_NS}primary_category")
    venue = category_el.get("term") if category_el is not None else None

    return PaperMetadata(
        title=title,
        authors=authors or ["Unknown"],
        year=year,
        venue=venue,
        abstract=abstract,
        doi=doi,
        arxiv_id=arxiv_id,
        source="arxiv",
        source_url=source_url,
        pdf_url=pdf_url,
        open_access=True,  # arXiv is always open access
    )


class ArxivSource(PaperSource):
    """arXiv Atom XML API adapter."""

    def __init__(self) -> None:
        self._limiter = RateLimiter(rate=3, per_seconds=1)  # 3 req/s

    async def search(
        self, query: str, filters: dict | None = None
    ) -> list[PaperMetadata]:
        filters = filters or {}
        max_results = min(filters.get("max_papers", 50), 200)

        search_query = f"all:{query}"

        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }

        await self._limiter.acquire()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(ARXIV_API_BASE, params=params)
            resp.raise_for_status()

        root = ET.fromstring(resp.text)
        papers = []
        for entry in root.findall(f"{ATOM_NS}entry"):
            parsed = _parse_entry(entry)
            if parsed:
                papers.append(parsed)

        logger.info(
            "source.search",
            source="arxiv",
            query=query,
            result_count=len(papers),
        )
        return papers

    async def get_paper(self, paper_id: str) -> PaperMetadata | None:
        params = {"id_list": paper_id, "max_results": 1}

        await self._limiter.acquire()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(ARXIV_API_BASE, params=params)
            resp.raise_for_status()

        root = ET.fromstring(resp.text)
        entries = root.findall(f"{ATOM_NS}entry")
        if not entries:
            return None
        return _parse_entry(entries[0])

    async def get_citations(self, paper_id: str) -> list[PaperMetadata]:
        # arXiv API does not support citation lookup
        return []

    async def get_references(self, paper_id: str) -> list[PaperMetadata]:
        # arXiv API does not support reference lookup
        return []
