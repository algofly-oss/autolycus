from fastapi import APIRouter, Request, Response, HTTPException
from pydantic import BaseModel
from shared.factory import db, redis
from ..auth.common import authenticate_user
from .common import MagnetDto, magnet_utils, pause_unfinished_torrents, update_to_db, copy_if_already_exists
from shared.modules.libtorrentx import LibTorrentSession
from bson import ObjectId
import asyncio
import datetime

router = APIRouter()

# On app reload, update status of any downloading torrent status to paused,
# as they may be killed already due to app reload
asyncio.create_task(pause_unfinished_torrents())

@router.post("/add")
async def add_torrent(dto: MagnetDto, request: Request):
    user_id = authenticate_user(request.cookies.get("session_token")).decode("utf-8")

    # extract info_hash from magnet
    info_hash = magnet_utils._clean_magnet_uri(dto.magnet).split(":")[3][:40]

    lt_session = LibTorrentSession(redis=redis)
    lt_session_eligible = False

    # add torrent to db
    already_exists = await db.torrents.find_one(
        {"info_hash": info_hash, "user_id": ObjectId(user_id)}, {"_id": True, "is_paused": True, "is_finished": True}
    )
    if already_exists:
        if already_exists.get("is_paused") and (not already_exists.get("is_finished")):
            await db.torrents.update_one(
                {"_id": already_exists.get("_id")},
                {"$set": {"is_paused": False, "is_finished": False}},
            )
            lt_session_eligible = True
    else:
        await db.torrents.insert_one(
            {
                "info_hash": info_hash,
                "user_id": ObjectId(user_id),
                "magnet": dto.magnet,
                "created_at": datetime.datetime.now(),
            }
        )
        lt_session_eligible = True

    if lt_session_eligible:
        redis.delete(f"{user_id}/{info_hash}/stop")
        redis.delete(f"{user_id}/{info_hash}/copied_from_existing")

        handle = lt_session.add_torrent(dto.magnet, f"/downloads/{user_id}")
        handle.set_callback(
            lambda props: update_to_db(props, ObjectId(user_id)),
            callback_interval=1,
            user_id=user_id,
        )

        return {"message": "Magnet Exists" if already_exists else "Magnet Added"}

    return {"message": "Magnet Exists"}
