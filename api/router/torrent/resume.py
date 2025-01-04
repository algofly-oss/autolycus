from fastapi import APIRouter, Request, HTTPException
from shared.factory import db, redis
from ..auth.common import authenticate_user
from .common import lt_session, update_to_db
from bson import ObjectId

router = APIRouter()

@router.post("/resume")
async def resume_torrent(info_hash: str, request: Request):
    user_id = authenticate_user(request.cookies.get("session_token"))
    torrent = await db.torrents.find_one(
        {"info_hash": info_hash},
        {"_id": True, "info_hash": True, "is_paused": True, "is_finished": True, "magnet": True},
    )

    lt_session_eligible = False

    if torrent:
        if torrent.get("is_paused") and (not torrent.get("is_finished")):
            await db.torrents.update_one(
                {"_id": torrent.get("_id")},
                {"$set": {"is_paused": False, "is_finished": False}},
            )
            lt_session_eligible = True

    if lt_session_eligible:
        redis.delete(f"{torrent['info_hash']}/stop")
        handle = lt_session.add_torrent(torrent.get("magnet"), "/downloads")
        handle.set_callback(
            lambda props: update_to_db(props, ObjectId(user_id.decode("utf-8"))),
            callback_interval=1,
        )

        return {"message": "Magnet Exists" if torrent else "Magnet Added"}

    raise HTTPException(status_code=400, detail="Unable to add torrent")

