import json
import asyncio
from fastapi import APIRouter, Request, HTTPException
from ..auth.common import authenticate_user
from fastapi.responses import StreamingResponse
from shared.factory import jackett

router = APIRouter()


@router.post("/search")
async def search_torrent(query: str, request: Request):
    authenticate_user(request.cookies.get("session_token"))

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


# @router.post("/search/get-magnet")
# async def search_torrent(data: dict, request: Request):
#     # Authenticate user
#     user_id = authenticate_user(request.cookies.get("session_token"))
#     magnet = torrent_search.get_magnet(data.get("data", {}))
#     return {"magnet": magnet}
