"""PubMed data source adapter using NCBI Entrez E-utilities.

API docs: https://www.ncbi.nlm.nih.gov/books/NBK25500/
Rate limit: 3 req/s without API key, 10 req/s with key.
"""

import xml.etree.ElementTree as ET

import httpx
import structlog

from app.schemas.paper import PaperMetadata
from app.sources.base import PaperSource
from app.sources.rate_limiter import RateLimiter

logger = structlog.stdlib.get_logger()

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _parse_pubmed_article(article_el: ET.Element) -> PaperMetadata | None:
    """Parse a PubmedArticle XML element into PaperMetadata."""
    medline = article_el.find("MedlineCitation")
    if medline is None:
        return None

    # PMID
    pmid_el = medline.find("PMID")
    pmid = pmid_el.text.strip() if pmid_el is not None and pmid_el.text else None

    article = medline.find("Article")
    if article is None:
        return None

    # Title
    title_el = article.find("ArticleTitle")
    if title_el is None or not title_el.text:
        return None
    title = title_el.text.strip()

    # Authors
    authors: list[str] = []
    author_list = article.find("AuthorList")
    if author_list is not None:
        for author_el in author_list.findall("Author"):
            last = author_el.find("LastName")
            fore = author_el.find("ForeName")
            if last is not None and last.text:
                name = last.text
                if fore is not None and fore.text:
                    name = f"{fore.text} {last.text}"
                authors.append(name)

    # Abstract
    abstract = None
    abstract_el = article.find("Abstract")
    if abstract_el is not None:
        parts = []
        for text_el in abstract_el.findall("AbstractText"):
            if text_el.text:
                label = text_el.get("Label")
                if label:
                    parts.append(f"{label}: {text_el.text.strip()}")
                else:
                    parts.append(text_el.text.strip())
        if parts:
            abstract = " ".join(parts)

    # Year
    year = None
    journal = article.find("Journal")
    if journal is not None:
        pub_date = journal.find("JournalIssue/PubDate")
        if pub_date is not None:
            year_el = pub_date.find("Year")
            if year_el is not None and year_el.text:
                try:
                    year = int(year_el.text)
                except ValueError:
                    pass
            # Fallback to MedlineDate
            if year is None:
                medline_date = pub_date.find("MedlineDate")
                if medline_date is not None and medline_date.text:
                    try:
                        year = int(medline_date.text[:4])
                    except ValueError:
                        pass

    # Venue (Journal title)
    venue = None
    if journal is not None:
        journal_title = journal.find("Title")
        if journal_title is not None and journal_title.text:
            venue = journal_title.text.strip()

    # DOI — from ArticleIdList in PubmedData
    doi = None
    pubmed_data = article_el.find("PubmedData")
    if pubmed_data is not None:
        id_list = pubmed_data.find("ArticleIdList")
        if id_list is not None:
            for aid in id_list.findall("ArticleId"):
                if aid.get("IdType") == "doi" and aid.text:
                    doi = aid.text.strip()
                    break

    # PMC ID
    pmcid = None
    if pubmed_data is not None:
        id_list = pubmed_data.find("ArticleIdList")
        if id_list is not None:
            for aid in id_list.findall("ArticleId"):
                if aid.get("IdType") == "pmc" and aid.text:
                    pmcid = aid.text.strip()
                    break

    # Source URL
    source_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None

    # PDF URL — PMC articles often have free full text
    pdf_url = None
    if pmcid:
        pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"

    return PaperMetadata(
        title=title,
        authors=authors or ["Unknown"],
        year=year,
        venue=venue,
        abstract=abstract,
        doi=doi,
        pmid=pmid,
        pmcid=pmcid,
        source="pubmed",
        source_url=source_url,
        pdf_url=pdf_url,
        open_access=pmcid is not None,  # PMC articles are typically OA
    )


class PubMedSource(PaperSource):
    """PubMed data source via NCBI Entrez E-utilities."""

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key
        rate = 10 if api_key else 3
        self._limiter = RateLimiter(rate=rate, per_seconds=1)

    def _base_params(self) -> dict:
        params: dict = {}
        if self._api_key:
            params["api_key"] = self._api_key
        return params

    async def search(
        self, query: str, filters: dict | None = None
    ) -> list[PaperMetadata]:
        filters = filters or {}
        retmax = min(filters.get("max_papers", 50), 200)

        # Step 1: esearch to get PMID list
        search_params = {
            **self._base_params(),
            "db": "pubmed",
            "term": query,
            "retmax": retmax,
            "retmode": "json",
            "sort": "relevance",
        }

        # Date range filter
        year_range = filters.get("year_range")
        if year_range:
            yr_min = year_range.get("min")
            yr_max = year_range.get("max")
            if yr_min:
                search_params["mindate"] = f"{yr_min}/01/01"
                search_params["datetype"] = "pdat"
            if yr_max:
                search_params["maxdate"] = f"{yr_max}/12/31"
                search_params["datetype"] = "pdat"

        await self._limiter.acquire()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{EUTILS_BASE}/esearch.fcgi", params=search_params
            )
            resp.raise_for_status()
            search_data = resp.json()

        id_list = search_data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            logger.info(
                "source.search", source="pubmed", query=query, result_count=0
            )
            return []

        # Step 2: efetch to get paper details
        papers = await self._fetch_by_pmids(id_list)
        logger.info(
            "source.search",
            source="pubmed",
            query=query,
            result_count=len(papers),
        )
        return papers

    async def get_paper(self, paper_id: str) -> PaperMetadata | None:
        papers = await self._fetch_by_pmids([paper_id])
        return papers[0] if papers else None

    async def get_citations(self, paper_id: str) -> list[PaperMetadata]:
        """Get papers that cite this paper via elink."""
        return await self._get_linked(paper_id, "pubmed_pubmed_citedin")

    async def get_references(self, paper_id: str) -> list[PaperMetadata]:
        """Get papers referenced by this paper via elink."""
        return await self._get_linked(paper_id, "pubmed_pubmed_refs")

    async def _fetch_by_pmids(
        self, pmids: list[str]
    ) -> list[PaperMetadata]:
        """Fetch full article details for a list of PMIDs."""
        if not pmids:
            return []

        fetch_params = {
            **self._base_params(),
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
        }

        await self._limiter.acquire()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{EUTILS_BASE}/efetch.fcgi", params=fetch_params
            )
            resp.raise_for_status()

        root = ET.fromstring(resp.text)
        papers = []
        for article_el in root.findall("PubmedArticle"):
            parsed = _parse_pubmed_article(article_el)
            if parsed:
                papers.append(parsed)
        return papers

    async def _get_linked(
        self, paper_id: str, linkname: str
    ) -> list[PaperMetadata]:
        """Get linked papers via elink, then fetch their details."""
        link_params = {
            **self._base_params(),
            "dbfrom": "pubmed",
            "db": "pubmed",
            "id": paper_id,
            "linkname": linkname,
            "retmode": "json",
        }

        await self._limiter.acquire()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{EUTILS_BASE}/elink.fcgi", params=link_params
            )
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            data = resp.json()

        # Extract linked PMIDs
        linked_pmids: list[str] = []
        linksets = data.get("linksets", [])
        for linkset in linksets:
            link_set_dbs = linkset.get("linksetdbs", [])
            for lsdb in link_set_dbs:
                if lsdb.get("linkname") == linkname:
                    links = lsdb.get("links", [])
                    linked_pmids.extend(str(lid) for lid in links[:100])

        if not linked_pmids:
            return []

        papers = await self._fetch_by_pmids(linked_pmids)
        logger.info(
            "source.get_related",
            source="pubmed",
            paper_id=paper_id,
            relation=linkname,
            result_count=len(papers),
        )
        return papers
