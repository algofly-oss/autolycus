from fastapi import APIRouter, Request, Response, HTTPException
from pydantic import BaseModel
from shared.factory import db, redis
from ..auth.common import authenticate_user
from .common import MagnetDto, lt_session, magnet_utils, pause_unfinished_torrents, update_to_db
from bson import ObjectId
import asyncio
import datetime

router = APIRouter()

# On app reload, update status of any downloading torrent status to paused,
# as they may be killed already due to app reload
asyncio.create_task(pause_unfinished_torrents())

@router.post("/add")
async def add_torrent(dto: MagnetDto, request: Request):
    user_id = authenticate_user(request.cookies.get("session_token"))

    # extract info_hash from magnet
    info_hash = magnet_utils._clean_magnet_uri(dto.magnet).split(":")[3][:40]

    lt_session_eligible = False

    # add torrent to db
    already_exists = await db.torrents.find_one(
        {"info_hash": info_hash}, {"_id": True, "is_paused": True, "is_finished": True}
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
                "user_id": ObjectId(user_id.decode("utf-8")),
                "magnet": dto.magnet,
                "created_at": datetime.datetime.now(),
            }
        )
        lt_session_eligible = True

    if lt_session_eligible:
        redis.delete(f"{info_hash}/stop")
        handle = lt_session.add_torrent(dto.magnet, "/downloads")
        handle.set_callback(
            lambda props: update_to_db(props, ObjectId(user_id.decode("utf-8"))),
            callback_interval=1,
        )

        return {"message": "Magnet Exists" if already_exists else "Magnet Added"}

    return {"message": "Magnet Exists"}
