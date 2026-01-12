import os
import hashlib
from fastapi import APIRouter, HTTPException, Request
from ..auth.common import authenticate_user
from pydantic import BaseModel
from shared.factory import db
from datetime import datetime
from .stream import handle_stream_file


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

    path_hash = hashlib.md5(payload.path.encode()).hexdigest()[:10]

    if not await db.public_urls.find_one(
        {"user_id": user_id.decode(), "info_hash": info_hash, "key": path_hash}
    ):
        await db.public_urls.insert_one(
            {
                "user_id": user_id.decode(),
                "key": path_hash,
                "path": payload.path,
                "info_hash": info_hash,
                "created_at": datetime.now(),
            }
        )

    return {"key": path_hash}


@router.get("/public/{key}")
async def public_file_access(request: Request, key: str, download: str = "false"):
    path = await db.public_urls.find_one({"key": key})
    if not path:
        raise HTTPException(status_code=404, detail="Public URL not found")

    path = path.get("path")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")

    download = download == "true" or download == "1"
    return handle_stream_file(request, path, download)
