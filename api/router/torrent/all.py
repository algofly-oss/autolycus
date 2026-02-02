from fastapi import APIRouter, Query, Request
from bson import ObjectId

from shared.factory import db
from shared.sockets import emit
from ..auth.common import authenticate_user
from ..files.status import get_disk_usage
from .download_status import get_download_status

router = APIRouter()


@router.get("/all")
async def all_torrent(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=500),
):
    user_id = authenticate_user(request.cookies.get("session_token"))
    if user_id:
        user_id = str(user_id.decode())

    user_oid = ObjectId(user_id)
    filter_query = {"user_id": user_oid}
    total_torrents = await db.torrents.count_documents(filter_query)
    skip = (page - 1) * page_size

    torrents = (
        await db.torrents.find(filter_query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(page_size)
        .to_list(length=page_size)
    )

    for torrent in torrents:
        del torrent["_id"]
        del torrent["user_id"]

    emit(f"/stc/disk-usage", get_disk_usage(user_id), user_id)
    emit(f"/stc/download_status", await get_download_status(user_id), user_id)

    return {
        "data": torrents,
        "meta": {"page": page, "page_size": page_size, "total": total_torrents},
    }
