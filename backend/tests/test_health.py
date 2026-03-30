"""Tests for health check endpoints."""

import pytest


@pytest.mark.asyncio
async def test_healthz(client):
    """GET /healthz should return 200 with status ok."""
    response = await client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_readyz_all_healthy(client):
    """GET /readyz should return 200 when all dependencies are ok."""
    response = await client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["redis"] == "ok"


@pytest.mark.asyncio
async def test_readyz_redis_down(client, mock_redis):
    """GET /readyz should return 503 when Redis is unreachable."""
    mock_redis.ping.side_effect = ConnectionError("Connection refused")
    response = await client.get("/readyz")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
    assert data["checks"]["redis"] == "error"
