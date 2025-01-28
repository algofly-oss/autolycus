from fastapi import APIRouter, Request, HTTPException
from shared.factory import db, redis
from ..auth.common import authenticate_user
from bson import ObjectId

router = APIRouter()


@router.post("/pause")
async def pause_torrent(info_hash: str, request: Request):
    user_id = authenticate_user(request.cookies.get("session_token")).decode("utf-8")
    torrent = await db.torrents.find_one(
        {"info_hash": info_hash, "user_id": ObjectId(user_id)},
        {"_id": True, "info_hash": True, "is_finished": True, "is_paused": True},
    )

    if torrent:
        db.torrents.update_one(
            {"_id": torrent["_id"]}, {"$set": {"is_paused": True, "is_finished": False}}
        )
        redis.set(f"{user_id}/{torrent['info_hash']}/stop", 1)
        return {"message": "success"}
    else:
        raise HTTPException(status_code=404, detail="Torrent not found")
