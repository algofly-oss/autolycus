from fastapi import APIRouter, Request, Response, HTTPException
from pydantic import BaseModel
from shared.factory import db, redis
from ..auth.common import authenticate_user
from .common import MagnetDto, lt_session, magnet_utils
from bson import ObjectId

router = APIRouter()


def update_to_db(props, user_id):
    props = props.asdict()
    props["user_id"] = user_id
    db.torrents.update_one({"info_hash": props["info_hash"]}, {"$set": props})


@router.post("/add")
async def add_torrent(dto: MagnetDto, request: Request):
    user_id = authenticate_user(request.cookies.get("session_token"))

    # extract info_hash from magnet
    info_hash = magnet_utils._clean_magnet_uri(dto.magnet).split(":")[3]

    # add torrent to db
    if not (await db.torrents.find_one({"info_hash": info_hash})):
        await db.torrents.insert_one({"info_hash": info_hash})

    handle = lt_session.add_torrent(dto.magnet, "/downloads")
    handle.set_callback(
        lambda props: update_to_db(props, ObjectId(user_id.decode("utf-8"))),
        callback_interval=1,
    )

    return {"message": "Magnet Added"}
