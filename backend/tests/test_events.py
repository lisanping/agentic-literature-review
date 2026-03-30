"""Tests for EventPublisher and EventBus — mocked Redis."""

import json

import pytest
from unittest.mock import AsyncMock, patch

from app.services.event_publisher import EventPublisher
from app.services.event_bus import EventBus, ReplayBuffer


# ── ReplayBuffer tests ──


def test_replay_buffer_append_and_replay():
    buf = ReplayBuffer(max_size=10)
    eid1 = buf.append("proj1", {"event_type": "progress", "data": {"n": 1}})
    eid2 = buf.append("proj1", {"event_type": "progress", "data": {"n": 2}})
    eid3 = buf.append("proj1", {"event_type": "complete", "data": {}})

    # Replay after first event
    missed = buf.replay_since("proj1", eid1)
    assert len(missed) == 2
    assert missed[0]["data"]["n"] == 2
    assert missed[1]["event_type"] == "complete"


def test_replay_buffer_replay_empty():
    buf = ReplayBuffer()
    missed = buf.replay_since("proj1", "nonexistent")
    assert missed == []


def test_replay_buffer_clear():
    buf = ReplayBuffer()
    buf.append("proj1", {"event_type": "progress"})
    buf.clear("proj1")
    missed = buf.replay_since("proj1", "0")
    assert missed == []


def test_replay_buffer_max_size():
    buf = ReplayBuffer(max_size=3)
    for i in range(5):
        buf.append("proj1", {"event_type": "progress", "i": i})
    # Only last 3 should remain
    all_events = buf.replay_since("proj1", "0")
    # event_id "0" won't be found (it was evicted), so we get nothing
    # But let's check the buffer directly
    assert len(buf._buffer["proj1"]) == 3


# ── EventPublisher tests ──


@pytest.mark.asyncio
async def test_event_publisher_publish():
    publisher = EventPublisher(redis_url="redis://fake:6379")
    mock_redis = AsyncMock()
    publisher._redis = mock_redis

    await publisher.publish(
        project_id="proj1",
        event_type="progress",
        agent_name="search",
        data={"completed": 5, "total": 10},
    )

    mock_redis.publish.assert_called_once()
    call_args = mock_redis.publish.call_args
    assert call_args[0][0] == "events:proj1"
    event = json.loads(call_args[0][1])
    assert event["event_type"] == "progress"
    assert event["agent_name"] == "search"
    assert event["data"]["completed"] == 5
