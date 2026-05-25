import json
import asyncio
from typing import AsyncGenerator
from sse_starlette.sse import EventSourceResponse

async def sse_generator(data_stream: AsyncGenerator[str, None]) -> AsyncGenerator[str, None]:
    """Wraps an async string generator into an SSE-compatible format."""
    async for token in data_stream:
        yield json.dumps({"token": token, "event": "delta"})
    yield json.dumps({"event": "done"})

def create_streaming_response(generator: AsyncGenerator[str, None]) -> EventSourceResponse:
    """Creates a FastAPI-compatible EventSourceResponse for streaming."""
    return EventSourceResponse(sse_generator(generator))
