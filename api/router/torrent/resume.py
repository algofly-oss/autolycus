from fastapi import APIRouter, Request, HTTPException
from shared.factory import db, redis
from ..auth.common import authenticate_user
from .common import update_to_db
from shared.modules.libtorrentx import LibTorrentSession
from bson import ObjectId

router = APIRouter()

@router.post("/resume")
async def resume_torrent(info_hash: str, request: Request):
    user_id = authenticate_user(request.cookies.get("session_token")).decode("utf-8")
    torrent = await db.torrents.find_one(
        {"info_hash": info_hash, "user_id": ObjectId(user_id)},
        {"_id": True, "info_hash": True, "is_paused": True, "is_finished": True, "magnet": True},
    )

    lt_session = LibTorrentSession(redis=redis)
    lt_session_eligible = False

    if torrent:
        if torrent.get("is_paused") and (not torrent.get("is_finished")):
            await db.torrents.update_one(
                {"_id": torrent.get("_id")},
                {"$set": {"is_paused": False, "is_finished": False}},
            )
            lt_session_eligible = True

    if lt_session_eligible:
        redis.delete(f"{user_id}/{torrent['info_hash']}/stop")
        redis.delete(f"{user_id}/{info_hash}/copied_from_existing")

        handle = lt_session.add_torrent(torrent.get("magnet"), f"/downloads/{user_id}")
        handle.set_callback(
            lambda props: update_to_db(props, ObjectId(user_id)),
            callback_interval=1,
            user_id=user_id,
        )

        return {"message": "Magnet Exists" if torrent else "Magnet Added"}

    raise HTTPException(status_code=400, detail="Unable to add torrent")

