from fastapi import APIRouter, HTTPException, Request
from ..auth.common import authenticate_user
from .playback import media_path
from starlette.responses import StreamingResponse, FileResponse
from pathlib import Path
import os
import mimetypes
import re
import asyncio
import time
from shared.factory import redis

router = APIRouter()


async def async_file_iterator(path, start=0, length=None, chunk_size=256 * 1024):
    with open(path, "rb") as f:
        f.seek(start)
        remaining = length
        last_active=0
        video=Path(path).suffix.lower() in {".mp4",".mkv",".avi",".webm",".m4v",".mov",".ts",".m2ts"}
        while True:
            if video and time.monotonic()-last_active>=15:
                redis.setex("media-playback-active",45,1);last_active=time.monotonic()
            if remaining is not None:
                if remaining <= 0:
                    break
                read_size = min(chunk_size, remaining)
            else:
                read_size = chunk_size

            data = f.read(read_size)
            if not data:
                break

            if remaining is not None:
                remaining -= len(data)

            yield data
            await asyncio.sleep(0)


def handle_stream_file(request, path, download=False):
    abs_path = media_path(path)

    if download:
        return FileResponse(abs_path, filename=abs_path.name)

    file_size = abs_path.stat().st_size
    range_header = request.headers.get("Range")

    mimetype = mimetypes.guess_type(abs_path)[0] or "application/octet-stream"

    # --------------------
    # NO RANGE -> FileResponse (zero RAM)
    # --------------------
    if not range_header:
        return StreamingResponse(async_file_iterator(abs_path,0,file_size),media_type=mimetype,
                                 headers={"Accept-Ranges":"bytes","Content-Length":str(file_size)})

    # --------------------
    # RANGE REQUEST
    # --------------------
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header)
    invalid = HTTPException(status_code=416, detail="Range not satisfiable", headers={"Content-Range": f"bytes */{file_size}"})
    if not match or not any(match.groups()):
        raise invalid
    if not match.group(1):
        suffix = int(match.group(2))
        if not suffix:
            raise invalid
        start, end = max(0, file_size - suffix), file_size - 1
    else:
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else file_size - 1
    if start >= file_size or end < start:
        raise invalid

    end = min(end, file_size - 1)
    length = end - start + 1

    return StreamingResponse(
        async_file_iterator(abs_path, start, length),
        status_code=206,
        media_type=mimetype,
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(length),
            "Accept-Ranges": "bytes",
        },
    )


@router.get("/stream")
async def stream_file(request: Request, path: str = "", download: bool = False):
    user_id = authenticate_user(request)
    return handle_stream_file(request, path, download)
