from fastapi import APIRouter, Request, HTTPException
from shared.factory import db, redis
from ..auth.common import authenticate_user

router = APIRouter()

@router.post("/pause")
async def pause_torrent(info_hash: str, request: Request):
    user_id = authenticate_user(request.cookies.get("session_token"))
    torrent = await db.torrents.find_one(
        {"info_hash": info_hash},
        {"_id": True, "info_hash": True, "is_finished": True, "is_paused": True},
    )

    if torrent:
        redis.set(f"{torrent['info_hash']}/stop", 1)
        return {"message": "success"}
    else:
        raise HTTPException(status_code=404, detail="Torrent not found")