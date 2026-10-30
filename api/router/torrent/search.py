import asyncio
import json

from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse

from ..auth.common import authenticate_user
from shared.factory import jackett

router = APIRouter()


@router.post("/search")
async def search_torrent(request: Request, query: str = Query(..., min_length=1, max_length=200), deep: bool = False):
    user_id = authenticate_user(request).decode()

    cancel_event = asyncio.Event()

    async def stream():
        iterator = jackett.search(query, cancel_event=cancel_event, user_id=user_id, deep=deep)
        pending = None
        try:
            while not cancel_event.is_set():
                if await request.is_disconnected():
                    break
                if pending is None:
                    pending = asyncio.create_task(iterator.__anext__())
                done, _ = await asyncio.wait({pending}, timeout=15)
                if not done:
                    # Keep the streaming connection alive while an indexer is busy.
                    yield json.dumps({"__type": "heartbeat"}) + "\n"
                    continue
                try:
                    item = pending.result()
                except StopAsyncIteration:
                    break
                pending = None
                yield json.dumps(item) + "\n"
        finally:
            cancel_event.set()
            if pending is not None:
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
            await iterator.aclose()

    return StreamingResponse(
        stream(),
        media_type="application/json",
    )
