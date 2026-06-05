import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ..auth.common import authenticate_user
from shared.factory import jackett

router = APIRouter()


@router.post("/search")
async def search_torrent(query: str, request: Request):
    authenticate_user(request)

    cancel_event = asyncio.Event()

    async def stream():
        try:
            async for item in jackett.search(query, cancel_event=cancel_event):
                if await request.is_disconnected():
                    cancel_event.set()
                    break

                yield json.dumps(item) + "\n"

        except asyncio.CancelledError:
            cancel_event.set()
            raise

        finally:
            cancel_event.set()

    return StreamingResponse(
        stream(),
        media_type="application/json",
    )
