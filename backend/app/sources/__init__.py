"""Data source initialization — assemble SourceRegistry at startup."""

import redis.asyncio as aioredis

from app.config import Settings
from app.sources.arxiv import ArxivSource
from app.sources.cache import CachedSource
from app.sources.registry import SourceRegistry
from app.sources.semantic_scholar import SemanticScholarSource


def create_source_registry(config: Settings) -> SourceRegistry:
    """Build and return a fully assembled SourceRegistry.

    MVP sources: Semantic Scholar + arXiv, both wrapped with Redis cache.
    """
    registry = SourceRegistry()
    cache = aioredis.from_url(config.REDIS_URL, decode_responses=True)

    registry.register(
        "semantic_scholar",
        CachedSource(
            SemanticScholarSource(api_key=config.S2_API_KEY),
            cache=cache,
        ),
    )
    registry.register(
        "arxiv",
        CachedSource(ArxivSource(), cache=cache),
    )

    return registry