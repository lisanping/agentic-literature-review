"""Shared pytest fixtures for the test suite."""

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db, get_redis
from app.main import app

# ── Async event loop ──


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Test database (in-memory SQLite) ──

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a test database session backed by in-memory SQLite."""
    # Import all models so Base.metadata knows about every table
    import app.models  # noqa: F401

    async with test_engine.begin() as conn:
        from app.models.database import Base

        await conn.run_sync(Base.metadata.create_all)

    async with test_session_factory() as session:
        yield session

    async with test_engine.begin() as conn:
        from app.models.database import Base

        await conn.run_sync(Base.metadata.drop_all)


# ── Mock Redis ──


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Return a mock Redis client."""
    mock = AsyncMock()
    mock.ping.return_value = True
    mock.get.return_value = None
    mock.set.return_value = True
    return mock


# ── FastAPI test client with dependency overrides ──


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
    mock_redis: AsyncMock,
) -> AsyncGenerator[AsyncClient, None]:
    """Yield an async HTTP client with overridden dependencies."""

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def _override_redis() -> AsyncMock:
        return mock_redis

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_redis] = _override_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def sync_client(
    db_session: AsyncSession,
    mock_redis: AsyncMock,
) -> TestClient:
    """Return a synchronous test client (for simple non-async tests)."""

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def _override_redis() -> AsyncMock:
        return mock_redis

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_redis] = _override_redis

    with TestClient(app) as tc:
        yield tc

    app.dependency_overrides.clear()
