"""Event publisher for Worker-side SSE events via Redis Pub/Sub — aligned with §6.4.1."""

import json
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis
import structlog

logger = structlog.stdlib.get_logger()


class EventPublisher:
    """Publish agent events from Celery Worker to Redis Pub/Sub channels.

    Channel pattern: ``events:{project_id}``
    """

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._redis: aioredis.Redis | None = None

    def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(
                self._redis_url, decode_responses=True
            )
        return self._redis

    async def publish(
        self,
        project_id: str,
        event_type: str,
        agent_name: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Publish an event to the project's Redis Pub/Sub channel."""
        event = {
            "event_type": event_type,
            "agent_name": agent_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data or {},
        }
        channel = f"events:{project_id}"
        r = self._get_redis()
        await r.publish(channel, json.dumps(event))
        logger.debug(
            "event.published",
            project_id=project_id,
            event_type=event_type,
            agent_name=agent_name,
        )

    async def close(self) -> None:
        if self._redis:
            await self._redis.close()
            self._redis = None
