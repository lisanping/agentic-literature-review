"""Dependency injection for API routes."""

from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# ── Database engine and session factory ──
engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

# ── Redis client ──
_redis_client: aioredis.Redis | None = None


def _get_redis_client() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
    return _redis_client


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_redis() -> aioredis.Redis:
    """Return the shared Redis client."""
    return _get_redis_client()
