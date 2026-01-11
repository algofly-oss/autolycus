import json
import asyncio
from fastapi import APIRouter, Request, HTTPException
from ..auth.common import authenticate_user
from fastapi.responses import StreamingResponse, Response
from shared.factory import jackett
import requests

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
