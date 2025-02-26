from fastapi import APIRouter, Request
from shared.factory import db
from bson import ObjectId
from ..auth.common import authenticate_user
from shared.sockets import emit
from .download_status import get_download_status
from ..files.status import get_disk_usage


router = APIRouter()


@router.get("/all")
async def all_torrent(request: Request):
    user_id = authenticate_user(request.cookies.get("session_token"))
    if user_id:
        user_id = str(user_id.decode())

    torrents = (
        await db.torrents.find({"user_id": ObjectId(user_id)})
        .sort("created_at", -1)
        .to_list(length=None)
    )

    # remove _id from each torrent
    for torrent in torrents:
        # torrent["_id"] = str(torrent["_id"])
        del torrent["_id"]
        del torrent["user_id"]

    emit(f"/stc/disk-usage", get_disk_usage(user_id), user_id)
    emit(f"/stc/download_status", await get_download_status(user_id), user_id)

    return {"data": torrents}
