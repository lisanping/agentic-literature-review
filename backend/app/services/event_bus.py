"""Event bus for Backend-side SSE consumption via Redis Pub/Sub — aligned with §6.4.2."""

import json
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

import redis.asyncio as aioredis
import structlog

logger = structlog.stdlib.get_logger()


class ReplayBuffer:
    """In-memory buffer of recent events for reconnection replay.

    Keeps the last ``max_size`` events per project so that clients
    reconnecting with ``Last-Event-ID`` can receive missed events.
    """

    def __init__(self, max_size: int = 100) -> None:
        self._buffer: dict[str, deque[dict]] = defaultdict(
            lambda: deque(maxlen=max_size)
        )
        self._counter: dict[str, int] = defaultdict(int)

    def append(self, project_id: str, event: dict) -> str:
        """Append an event, assigning it a monotonic event_id. Returns the event_id."""
        self._counter[project_id] += 1
        event_id = str(self._counter[project_id])
        event["event_id"] = event_id
        self._buffer[project_id].append(event)
        return event_id

    def replay_since(
        self, project_id: str, last_event_id: str
    ) -> list[dict]:
        """Return events that occurred after the given event_id."""
        events = self._buffer.get(project_id, deque())
        result: list[dict] = []
        found = False
        for e in events:
            if found:
                result.append(e)
            elif e.get("event_id") == last_event_id:
                found = True
        return result

    def clear(self, project_id: str) -> None:
        """Clear buffer for a project."""
        self._buffer.pop(project_id, None)
        self._counter.pop(project_id, None)


class EventBus:
    """Subscribe to project events via Redis Pub/Sub.

    Used by the SSE endpoint to stream events to the frontend / CLI.
    """

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url

    async def subscribe(
        self, project_id: str
    ) -> AsyncGenerator[dict, None]:
        """Async generator that yields events for a project.

        Listens on Redis Pub/Sub channel ``events:{project_id}`` and yields
        parsed event dicts. Terminates when a ``complete`` event is received.
        """
        r = aioredis.from_url(self._redis_url, decode_responses=True)
        pubsub = r.pubsub()
        channel = f"events:{project_id}"
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    event = json.loads(message["data"])
                except (json.JSONDecodeError, TypeError):
                    continue
                yield event
                if event.get("event_type") == "complete":
                    break
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
            await r.close()
