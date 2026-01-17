from fastapi import APIRouter, Request, HTTPException
from shared.factory import db, redis
from ..auth.common import authenticate_user
from bson import ObjectId
from shared.sockets import emit
from .download_status import get_download_status

router = APIRouter()


@router.post("/pause")
async def pause_torrent(info_hash: str, request: Request):
    user_id = authenticate_user(request.cookies.get("session_token")).decode("utf-8")

    if info_hash.startswith("url_hash_"):
        url_hash = info_hash.lstrip("url_hash_")
        torrent = await db.torrents.find_one(
            {"url_hash": url_hash, "user_id": ObjectId(user_id)},
        )
        if torrent:
            db.torrents.update_one(
                {"_id": torrent["_id"]},
                {
                    "$set": {
                        "is_paused": True,
                        "download_speed": 0,
                    }
                },
            )
            key = f"{user_id}/{torrent['url_hash']}/stop"
            redis.set(key, 1)
            emit(
                f"/stc/torrent-added-or-removed",
                {"action": "paused", "url_hash": url_hash},
                user_id,
            )
            return {"message": "success"}

        raise HTTPException(status_code=404, detail="Torrent not found")

    else:
        torrent = await db.torrents.find_one(
            {"info_hash": info_hash, "user_id": ObjectId(user_id)},
            {"_id": True, "info_hash": True, "is_finished": True, "is_paused": True},
        )

        if torrent:
            db.torrents.update_one(
                {"_id": torrent["_id"]},
                {"$set": {"is_paused": True, "is_finished": False}},
            )
            redis.set(f"{user_id}/{torrent['info_hash']}/stop", 1)
            return {"message": "success"}

        raise HTTPException(status_code=404, detail="Torrent not found")
