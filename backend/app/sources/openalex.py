"""OpenAlex data source adapter.

API docs: https://docs.openalex.org
Rate limit: 10 req/s with polite pool (mailto), 1 req/s without.
"""

import httpx
import structlog

from app.schemas.paper import PaperMetadata
from app.sources.base import PaperSource
from app.sources.rate_limiter import RateLimiter

logger = structlog.stdlib.get_logger()

OPENALEX_API_BASE = "https://api.openalex.org"


def _reconstruct_abstract(inverted_index: dict | None) -> str | None:
    """Reconstruct abstract text from OpenAlex inverted index format.

    The inverted index maps words to their positions:
      {"word1": [0, 5], "word2": [1]} -> "word1 word2 ... word1"
    """
    if not inverted_index:
        return None
    try:
        position_word: list[tuple[int, str]] = []
        for word, positions in inverted_index.items():
            for pos in positions:
                position_word.append((pos, word))
        position_word.sort(key=lambda x: x[0])
        return " ".join(word for _, word in position_word)
    except Exception:
        return None


def _extract_openalex_id(openalex_url: str) -> str:
    """Extract the OpenAlex Work ID from the full URL.

    Example: "https://openalex.org/W2741809807" -> "W2741809807"
    """
    if "/" in openalex_url:
        return openalex_url.rsplit("/", 1)[-1]
    return openalex_url


def _parse_work(data: dict) -> PaperMetadata | None:
    """Parse an OpenAlex Work object into PaperMetadata."""
    if not data or not data.get("title"):
        return None

    # Authors
    authorships = data.get("authorships") or []
    authors = []
    for a in authorships:
        author = a.get("author", {})
        name = author.get("display_name")
        if name:
            authors.append(name)

    # DOI — strip the https://doi.org/ prefix
    doi_raw = data.get("doi")
    doi = None
    if doi_raw:
        doi = doi_raw.replace("https://doi.org/", "").strip()
        if not doi:
            doi = None

    # PDF URL
    pdf_url = None
    primary_loc = data.get("primary_location") or {}
    if primary_loc.get("pdf_url"):
        pdf_url = primary_loc["pdf_url"]
    elif primary_loc.get("is_oa"):
        # Try best_oa_location
        best_oa = data.get("best_oa_location") or {}
        pdf_url = best_oa.get("pdf_url")

    # Venue
    venue = None
    source_info = primary_loc.get("source") or {}
    if source_info.get("display_name"):
        venue = source_info["display_name"]

    # Abstract
    abstract = _reconstruct_abstract(data.get("abstract_inverted_index"))

    # Open access
    oa_info = data.get("open_access") or {}
    open_access = bool(oa_info.get("is_oa"))

    # OpenAlex ID
    openalex_id = _extract_openalex_id(data.get("id", ""))

    return PaperMetadata(
        title=data["title"],
        authors=authors or ["Unknown"],
        year=data.get("publication_year"),
        venue=venue,
        abstract=abstract,
        doi=doi,
        openalex_id=openalex_id or None,
        citation_count=data.get("cited_by_count", 0) or 0,
        reference_count=data.get("referenced_works_count", 0) or 0,
        source="openalex",
        source_url=data.get("id"),
        pdf_url=pdf_url,
        open_access=open_access,
    )


class OpenAlexSource(PaperSource):
    """OpenAlex data source — open academic metadata."""

    def __init__(self, email: str = "") -> None:
        self._email = email
        # Polite pool if email provided
        rate = 10 if email else 1
        self._limiter = RateLimiter(rate=rate, per_seconds=1)

    def _params(self, extra: dict | None = None) -> dict:
        """Build request params with optional mailto."""
        params = {}
        if self._email:
            params["mailto"] = self._email
        if extra:
            params.update(extra)
        return params

    async def search(
        self, query: str, filters: dict | None = None
    ) -> list[PaperMetadata]:
        filters = filters or {}
        per_page = min(filters.get("max_papers", 50), 200)

        params = self._params({"search": query, "per_page": per_page})

        # Build filter string
        filter_parts: list[str] = []
        year_range = filters.get("year_range")
        if year_range:
            yr_min = year_range.get("min")
            yr_max = year_range.get("max")
            if yr_min and yr_max:
                filter_parts.append(f"publication_year:{yr_min}-{yr_max}")
            elif yr_min:
                filter_parts.append(f"publication_year:>{yr_min - 1}")
            elif yr_max:
                filter_parts.append(f"publication_year:<{yr_max + 1}")

        if filters.get("open_access"):
            filter_parts.append("open_access.is_oa:true")

        if filter_parts:
            params["filter"] = ",".join(filter_parts)

        await self._limiter.acquire()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{OPENALEX_API_BASE}/works", params=params)
            resp.raise_for_status()
            data = resp.json()

        papers = []
        for item in data.get("results", []):
            parsed = _parse_work(item)
            if parsed:
                papers.append(parsed)

        logger.info(
            "source.search",
            source="openalex",
            query=query,
            result_count=len(papers),
        )
        return papers

    async def get_paper(self, paper_id: str) -> PaperMetadata | None:
        await self._limiter.acquire()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{OPENALEX_API_BASE}/works/{paper_id}",
                params=self._params(),
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return _parse_work(resp.json())

    async def get_citations(self, paper_id: str) -> list[PaperMetadata]:
        """Get papers that cite this paper."""
        return await self._get_related(paper_id, "cited_by")

    async def get_references(self, paper_id: str) -> list[PaperMetadata]:
        """Get papers referenced by this paper."""
        return await self._get_related(paper_id, "cites")

    async def _get_related(
        self, paper_id: str, relation: str
    ) -> list[PaperMetadata]:
        await self._limiter.acquire()
        params = self._params(
            {"filter": f"{relation}:{paper_id}", "per_page": 100}
        )
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{OPENALEX_API_BASE}/works", params=params
            )
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            data = resp.json()

        papers = []
        for item in data.get("results", []):
            parsed = _parse_work(item)
            if parsed:
                papers.append(parsed)

        logger.info(
            "source.get_related",
            source="openalex",
            paper_id=paper_id,
            relation=relation,
            result_count=len(papers),
        )
        return papers
