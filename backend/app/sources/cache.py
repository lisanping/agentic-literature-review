"""Redis caching decorator for PaperSource — aligned with §9.4."""

import hashlib
import json

import structlog
from redis.asyncio import Redis

from app.schemas.paper import PaperMetadata
from app.sources.base import PaperSource

logger = structlog.stdlib.get_logger()


class CachedSource(PaperSource):
    """Wraps a PaperSource with Redis caching.

    Caches search results, paper details, citations, and references.
    Default TTL is 24 hours.
    """

    def __init__(
        self, source: PaperSource, cache: Redis, ttl: int = 86400
    ) -> None:
        self.source = source
        self.cache = cache
        self.ttl = ttl
        self._source_name = source.__class__.__name__

    def _make_key(self, prefix: str, raw: str) -> str:
        query_hash = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return f"{prefix}:{self._source_name}:{query_hash}"

    async def _get_cached(self, key: str) -> list[dict] | None:
        try:
            data = await self.cache.get(key)
            if data:
                return json.loads(data)
        except Exception:
            logger.debug("cache.get_failed", key=key)
        return None

    async def _set_cached(self, key: str, items: list[dict]) -> None:
        try:
            await self.cache.set(key, json.dumps(items), ex=self.ttl)
        except Exception:
            logger.debug("cache.set_failed", key=key)

    async def search(
        self, query: str, filters: dict | None = None
    ) -> list[PaperMetadata]:
        raw = json.dumps({"q": query, "f": filters or {}}, sort_keys=True)
        key = self._make_key("search", raw)

        cached = await self._get_cached(key)
        if cached is not None:
            logger.debug("cache.hit", key=key)
            return [PaperMetadata(**item) for item in cached]

        results = await self.source.search(query, filters)
        await self._set_cached(key, [r.model_dump() for r in results])
        return results

    async def get_paper(self, paper_id: str) -> PaperMetadata | None:
        key = self._make_key("paper", paper_id)
        cached = await self._get_cached(key)
        if cached is not None:
            return PaperMetadata(**cached[0]) if cached else None

        result = await self.source.get_paper(paper_id)
        if result:
            await self._set_cached(key, [result.model_dump()])
        return result

    async def get_citations(self, paper_id: str) -> list[PaperMetadata]:
        key = self._make_key("citations", paper_id)
        cached = await self._get_cached(key)
        if cached is not None:
            return [PaperMetadata(**item) for item in cached]

        results = await self.source.get_citations(paper_id)
        await self._set_cached(key, [r.model_dump() for r in results])
        return results

    async def get_references(self, paper_id: str) -> list[PaperMetadata]:
        key = self._make_key("references", paper_id)
        cached = await self._get_cached(key)
        if cached is not None:
            return [PaperMetadata(**item) for item in cached]

        results = await self.source.get_references(paper_id)
        await self._set_cached(key, [r.model_dump() for r in results])
        return results
