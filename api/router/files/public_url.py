import os
import hashlib
from fastapi import APIRouter, HTTPException, Request
from ..auth.common import authenticate_user
from pydantic import BaseModel
from shared.factory import db
from shared.modules.torrent_name_parser import parse_title
from datetime import datetime
from .stream import handle_stream_file
import traceback

router = APIRouter()


class Payload(BaseModel):
    path: str


@router.post("/generate-public-url")
async def generate_public_url(payload: Payload, request: Request):
    user_id = authenticate_user(request.cookies.get("session_token"))
    path_user_id = payload.path.split("/")[2]
    info_hash = payload.path.split("/")[3]

    if path_user_id != user_id.decode():
        raise HTTPException(status_code=403, detail="Access denied")

    if not os.path.exists(payload.path):
        raise HTTPException(status_code=404, detail="Path not found")

    torrent_name = ""
    torrent = await db.torrents.find_one({"info_hash": info_hash})
    if torrent:
        torrent_name = torrent.get("name")

    path_hash = hashlib.md5(f"{info_hash}/{payload.path}".encode()).hexdigest()[:10]

    try:
        title = parse_title(torrent_name + " " + os.path.basename(payload.path))
        title, ext = os.path.splitext(title)
        title = f"{title}-{path_hash}{ext}"
    except Exception as e:
        title = path_hash
        traceback.print_exc()

    if not await db.public_urls.find_one(
        {"user_id": user_id.decode(), "info_hash": info_hash, "path_hash": path_hash}
    ):
        await db.public_urls.insert_one(
            {
                "user_id": user_id.decode(),
                "info_hash": info_hash,
                "path_hash": path_hash,
                "path": payload.path,
                "title": title,
                "created_at": datetime.now(),
            }
        )

    return {"key": title}


@router.get("/public/{key}")
async def public_file_access(request: Request, key: str, download: str = "false"):
    path = await db.public_urls.find_one(
        {
            "$or": [
                {"title": key},
                {"path_hash": key},
            ]
        }
    )
    if not path:
        raise HTTPException(status_code=404, detail="Public URL not found")

    path = path.get("path")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")

    download = download == "true" or download == "1"
    return handle_stream_file(request, path, download)
