"""Tests for data source components — registry, rate limiter, cached source."""

import asyncio

import pytest
from unittest.mock import AsyncMock

from app.schemas.paper import PaperMetadata
from app.sources.base import PaperSource
from app.sources.registry import SourceRegistry
from app.sources.rate_limiter import RateLimiter
from app.sources.cache import CachedSource


# ── Fake source for testing ──

class FakeSource(PaperSource):
    def __init__(self, papers=None):
        self.papers = papers or []
        self.search_call_count = 0

    async def search(self, query, filters=None):
        self.search_call_count += 1
        return self.papers

    async def get_paper(self, paper_id):
        return self.papers[0] if self.papers else None

    async def get_citations(self, paper_id):
        return []

    async def get_references(self, paper_id):
        return []


# ── SourceRegistry tests ──


def test_registry_register_and_get():
    reg = SourceRegistry()
    src = FakeSource()
    reg.register("test", src)
    assert reg.get_source("test") is src


def test_registry_enabled_sources():
    reg = SourceRegistry()
    src1 = FakeSource()
    src2 = FakeSource()
    reg.register("a", src1, enabled=True)
    reg.register("b", src2, enabled=False)
    enabled = reg.get_enabled_sources()
    assert len(enabled) == 1
    assert enabled[0][0] == "a"


def test_registry_enable_disable():
    reg = SourceRegistry()
    src = FakeSource()
    reg.register("test", src, enabled=False)
    assert len(reg.get_enabled_sources()) == 0
    reg.enable("test")
    assert len(reg.get_enabled_sources()) == 1
    reg.disable("test")
    assert len(reg.get_enabled_sources()) == 0


def test_registry_unregister():
    reg = SourceRegistry()
    reg.register("test", FakeSource())
    reg.unregister("test")
    assert reg.get_source("test") is None
    assert len(reg.get_enabled_sources()) == 0


def test_registry_get_nonexistent():
    reg = SourceRegistry()
    assert reg.get_source("nope") is None


# ── RateLimiter tests ──


@pytest.mark.asyncio
async def test_rate_limiter_allows_within_rate():
    limiter = RateLimiter(rate=10, per_seconds=1)
    # Should complete quickly without blocking
    for _ in range(5):
        await limiter.acquire()


@pytest.mark.asyncio
async def test_rate_limiter_refills_tokens():
    limiter = RateLimiter(rate=100, per_seconds=1)
    # Drain several tokens
    for _ in range(10):
        await limiter.acquire()
    # Should still have tokens
    await limiter.acquire()


# ── CachedSource tests ──


@pytest.mark.asyncio
async def test_cached_source_caches_search():
    """First call should go to source, second should hit cache."""
    paper = PaperMetadata(
        title="Test Paper", authors=["Author"], source="arxiv"
    )
    inner = FakeSource(papers=[paper])

    mock_cache = AsyncMock()
    mock_cache.get.return_value = None  # cache miss first time

    cached = CachedSource(inner, cache=mock_cache, ttl=3600)
    result = await cached.search("test query")

    assert len(result) == 1
    assert result[0].title == "Test Paper"
    assert inner.search_call_count == 1
    # Should have called cache.set
    mock_cache.set.assert_called_once()


@pytest.mark.asyncio
async def test_cached_source_returns_from_cache():
    """When cache has data, should return it without calling the source."""
    import json

    paper_data = [{"title": "Cached Paper", "authors": ["A"], "source": "arxiv"}]

    inner = FakeSource()
    mock_cache = AsyncMock()
    mock_cache.get.return_value = json.dumps(paper_data)

    cached = CachedSource(inner, cache=mock_cache, ttl=3600)
    result = await cached.search("test query")

    assert len(result) == 1
    assert result[0].title == "Cached Paper"
    assert inner.search_call_count == 0  # source was NOT called


@pytest.mark.asyncio
async def test_cached_source_get_paper():
    paper = PaperMetadata(title="P", authors=["A"], source="arxiv")
    inner = FakeSource(papers=[paper])
    mock_cache = AsyncMock()
    mock_cache.get.return_value = None

    cached = CachedSource(inner, cache=mock_cache, ttl=3600)
    result = await cached.get_paper("123")
    assert result is not None
    assert result.title == "P"
