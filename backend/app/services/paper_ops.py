"""Paper deduplication utilities — aligned with data-model.md §4.2."""

import re
import unicodedata

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.schemas.paper import PaperMetadata


def normalize_title(title: str) -> str:
    """Normalize a paper title for fuzzy matching.

    Lowercases, strips accents, removes punctuation and extra whitespace.
    """
    title = title.lower().strip()
    # Remove accents
    title = unicodedata.normalize("NFKD", title)
    title = "".join(c for c in title if not unicodedata.combining(c))
    # Remove punctuation
    title = re.sub(r"[^\w\s]", "", title)
    # Collapse whitespace
    title = re.sub(r"\s+", " ", title).strip()
    return title


def title_similarity(a: str, b: str) -> float:
    """Compute similarity between two titles using normalized token overlap.

    Returns a float between 0.0 and 1.0.
    """
    tokens_a = set(normalize_title(a).split())
    tokens_b = set(normalize_title(b).split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def _merge_metadata(existing: Paper, metadata: PaperMetadata) -> Paper:
    """Merge new metadata into an existing paper record.

    Fills in missing fields without overwriting existing data, and updates
    citation count if the new value is higher.
    """
    if not existing.doi and metadata.doi:
        existing.doi = metadata.doi
    if not existing.s2_id and metadata.s2_id:
        existing.s2_id = metadata.s2_id
    if not existing.arxiv_id and metadata.arxiv_id:
        existing.arxiv_id = metadata.arxiv_id
    if not existing.abstract and metadata.abstract:
        existing.abstract = metadata.abstract
    if not existing.pdf_url and metadata.pdf_url:
        existing.pdf_url = metadata.pdf_url
    if not existing.venue and metadata.venue:
        existing.venue = metadata.venue
    if not existing.year and metadata.year:
        existing.year = metadata.year
    if metadata.citation_count > existing.citation_count:
        existing.citation_count = metadata.citation_count
    if metadata.reference_count > existing.reference_count:
        existing.reference_count = metadata.reference_count
    if metadata.open_access and not existing.open_access:
        existing.open_access = True
    return existing


async def find_or_create_paper(
    db: AsyncSession, metadata: PaperMetadata
) -> Paper:
    """Find an existing paper or create a new record, ensuring deduplication.

    Matching priority:
      1. DOI exact match (most reliable)
      2. Semantic Scholar ID match
      3. arXiv ID match
      4. Title fuzzy match (normalized similarity > 0.95)
    """
    # 1. DOI match
    if metadata.doi:
        result = await db.execute(
            select(Paper).where(Paper.doi == metadata.doi)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return _merge_metadata(existing, metadata)

    # 2. S2 ID match
    if metadata.s2_id:
        result = await db.execute(
            select(Paper).where(Paper.s2_id == metadata.s2_id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return _merge_metadata(existing, metadata)

    # 3. arXiv ID match
    if metadata.arxiv_id:
        result = await db.execute(
            select(Paper).where(Paper.arxiv_id == metadata.arxiv_id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return _merge_metadata(existing, metadata)

    # 4. Title fuzzy match (last resort)
    normalized = normalize_title(metadata.title)
    # Use the first 50 chars as a coarse filter to avoid full table scan
    result = await db.execute(
        select(Paper).where(
            func.lower(Paper.title).contains(normalized[:50])
        )
    )
    candidates = result.scalars().all()
    for candidate in candidates:
        if title_similarity(candidate.title, metadata.title) > 0.95:
            return _merge_metadata(candidate, metadata)

    # No match found — create new record
    paper = Paper(
        title=metadata.title,
        authors=metadata.authors,
        year=metadata.year,
        venue=metadata.venue,
        abstract=metadata.abstract,
        doi=metadata.doi,
        s2_id=metadata.s2_id,
        arxiv_id=metadata.arxiv_id,
        citation_count=metadata.citation_count,
        reference_count=metadata.reference_count,
        source=metadata.source,
        source_url=metadata.source_url or metadata.url,
        pdf_url=metadata.pdf_url,
        open_access=metadata.open_access,
    )
    db.add(paper)
    await db.flush()
    return paper
