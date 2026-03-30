"""Semantic Scholar data source adapter.

API docs: https://api.semanticscholar.org/api-docs/graph
Rate limit: 100 requests / 5 minutes (without API key).
"""

import httpx
import structlog

from app.schemas.paper import PaperMetadata
from app.sources.base import PaperSource
from app.sources.rate_limiter import RateLimiter

logger = structlog.stdlib.get_logger()

S2_API_BASE = "https://api.semanticscholar.org/graph/v1"
S2_SEARCH_FIELDS = (
    "paperId,externalIds,title,authors,year,venue,abstract,"
    "citationCount,referenceCount,isOpenAccess,openAccessPdf,url"
)
S2_CITATION_FIELDS = (
    "paperId,externalIds,title,authors,year,venue,abstract,"
    "citationCount,referenceCount,isOpenAccess,openAccessPdf,url"
)


def _parse_paper(data: dict) -> PaperMetadata | None:
    """Parse a Semantic Scholar API paper object into PaperMetadata."""
    if not data or not data.get("title"):
        return None

    external_ids = data.get("externalIds") or {}
    authors_raw = data.get("authors") or []
    authors = [a.get("name", "") for a in authors_raw if a.get("name")]

    pdf_url = None
    oa_pdf = data.get("openAccessPdf")
    if oa_pdf and isinstance(oa_pdf, dict):
        pdf_url = oa_pdf.get("url")

    return PaperMetadata(
        title=data["title"],
        authors=authors or ["Unknown"],
        year=data.get("year"),
        venue=data.get("venue") or None,
        abstract=data.get("abstract"),
        doi=external_ids.get("DOI"),
        s2_id=data.get("paperId"),
        arxiv_id=external_ids.get("ArXiv"),
        citation_count=data.get("citationCount", 0) or 0,
        reference_count=data.get("referenceCount", 0) or 0,
        source="semantic_scholar",
        source_url=data.get("url"),
        pdf_url=pdf_url,
        open_access=bool(data.get("isOpenAccess")),
    )


class SemanticScholarSource(PaperSource):
    """Semantic Scholar Graph API adapter."""

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key
        self._limiter = RateLimiter(rate=100, per_seconds=300)  # 100 req / 5 min
        self._headers: dict[str, str] = {}
        if api_key:
            self._headers["x-api-key"] = api_key

    async def search(
        self, query: str, filters: dict | None = None
    ) -> list[PaperMetadata]:
        filters = filters or {}
        params: dict = {
            "query": query,
            "fields": S2_SEARCH_FIELDS,
            "limit": min(filters.get("max_papers", 50), 100),
        }

        # Year range filter
        year_range = filters.get("year_range")
        if year_range:
            yr_min = year_range.get("min", "")
            yr_max = year_range.get("max", "")
            if yr_min or yr_max:
                params["year"] = f"{yr_min}-{yr_max}"

        await self._limiter.acquire()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{S2_API_BASE}/paper/search",
                params=params,
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json()

        papers = []
        for item in data.get("data", []):
            parsed = _parse_paper(item)
            if parsed:
                papers.append(parsed)

        logger.info(
            "source.search",
            source="semantic_scholar",
            query=query,
            result_count=len(papers),
        )
        return papers

    async def get_paper(self, paper_id: str) -> PaperMetadata | None:
        await self._limiter.acquire()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{S2_API_BASE}/paper/{paper_id}",
                params={"fields": S2_SEARCH_FIELDS},
                headers=self._headers,
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return _parse_paper(resp.json())

    async def get_citations(self, paper_id: str) -> list[PaperMetadata]:
        return await self._get_related(paper_id, "citations")

    async def get_references(self, paper_id: str) -> list[PaperMetadata]:
        return await self._get_related(paper_id, "references")

    async def _get_related(
        self, paper_id: str, relation: str
    ) -> list[PaperMetadata]:
        """Fetch citations or references for a paper."""
        await self._limiter.acquire()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{S2_API_BASE}/paper/{paper_id}/{relation}",
                params={"fields": S2_CITATION_FIELDS, "limit": 100},
                headers=self._headers,
            )
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            data = resp.json()

        papers = []
        for item in data.get("data", []):
            # Citations/references are nested under "citingPaper" / "citedPaper"
            inner_key = "citingPaper" if relation == "citations" else "citedPaper"
            inner = item.get(inner_key, item)
            parsed = _parse_paper(inner)
            if parsed:
                papers.append(parsed)

        logger.info(
            "source.get_related",
            source="semantic_scholar",
            paper_id=paper_id,
            relation=relation,
            result_count=len(papers),
        )
        return papers
