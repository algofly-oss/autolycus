import json
import asyncio
from fastapi import APIRouter, Request, HTTPException
from ..auth.common import authenticate_user
from fastapi.responses import StreamingResponse, RedirectResponse
from shared.factory import jackett
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

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


@router.get("/search/imdb-redirect")
async def search_imdb_title(q: str, request: Request):
    authenticate_user(request.cookies.get("session_token"))
    url = f"https://www.imdb.com/find/?q={quote_plus(q)}&s=tt"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    section = soup.select_one('section[data-testid="find-results-section-title"]')
    if not section:
        return None

    link = section.select_one('a[href^="/title/"]')
    if not link:
        return None

    return RedirectResponse("https://www.imdb.com" + link["href"].split("?")[0])
