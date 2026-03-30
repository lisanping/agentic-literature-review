"""SSE event stream endpoint — §8.3.5."""

import json

from fastapi import APIRouter, Header
from starlette.responses import StreamingResponse

from app.config import settings
from app.services.event_bus import EventBus, ReplayBuffer

router = APIRouter(tags=["events"])

# Shared replay buffer (in-process; fine for single-server MVP)
_replay_buffer = ReplayBuffer(max_size=200)


def _format_sse(event: dict) -> str:
    """Format an event dict as an SSE text chunk."""
    event_id = event.get("id", "")
    event_type = event.get("event_type", "message")
    data = json.dumps(event, ensure_ascii=False)
    lines = [
        f"id: {event_id}",
        f"event: {event_type}",
        f"data: {data}",
        "",
        "",
    ]
    return "\n".join(lines)


@router.get("/api/v1/projects/{project_id}/events")
async def sse_stream(
    project_id: str,
    last_event_id: str | None = Header(None, alias="Last-Event-ID"),
) -> StreamingResponse:
    """Server-Sent Events stream for real-time workflow progress.

    Supports ``Last-Event-ID`` header for replay of missed events.
    The stream terminates when a ``complete`` or ``error`` event is received.
    """

    async def event_generator():
        # Replay missed events
        if last_event_id:
            missed = _replay_buffer.replay_since(project_id, last_event_id)
            for event in missed:
                yield _format_sse(event)

        # Subscribe to live events
        bus = EventBus(settings.REDIS_URL)
        try:
            async for event in bus.subscribe(project_id):
                event_id = _replay_buffer.append(project_id, event)
                event["id"] = event_id
                yield _format_sse(event)
        finally:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
