from fastapi import APIRouter, Request
from shared.factory import db
from bson import ObjectId
from ..auth.common import authenticate_user

router = APIRouter()

@router.post("/all")
async def all_torrent(request: Request):
    user_id = authenticate_user(request.cookies.get("session_token"))
    torrents = await db.torrents.find({"user_id": ObjectId(user_id.decode("utf-8"))}).to_list(length=None)

    # remove _id from each torrent
    for torrent in torrents:
        del torrent["_id"]
        del torrent["user_id"]

    return {"data": torrents}
