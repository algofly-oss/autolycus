from fastapi import APIRouter, Request, HTTPException
from shared.factory import db
from ..auth.common import authenticate_user
from .common import MagnetDto, magnet_utils

router = APIRouter()


@router.post("/get")
async def get_torrent(dto: MagnetDto, request: Request):
    user_id = authenticate_user(request.cookies.get("session_token"))

    # extract info_hash from magnet
    info_hash = magnet_utils._clean_magnet_uri(dto.magnet).split(":")[3][:40]

    # add torrent to db
    torrent = await db.torrents.find_one({"info_hash": info_hash})

    if not torrent:
        raise HTTPException(status_code=400, detail="Torrent not found")

    return {
        "info_hash": torrent["info_hash"],
        "download_speed": torrent["download_speed"],
        "downloaded_bytes": torrent["downloaded_bytes"],
        "is_finished": torrent["is_finished"],
        "is_paused": torrent["is_paused"],
        "name": torrent["name"],
        "num_connections": torrent["num_connections"],
        "num_peers": torrent["num_peers"],
        "num_seeds": torrent["num_seeds"],
        "num_trackers": torrent["num_trackers"],
        "ok": torrent["ok"],
        "progress": torrent["progress"],
        "queue_position": torrent["queue_position"],
        "save_dir": torrent["save_dir"],
        "total_bytes": torrent["total_bytes"],
        "upload_speed": torrent["upload_speed"],
    }
