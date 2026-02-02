from fastapi import APIRouter, HTTPException, Request
from ..auth.common import authenticate_user
from starlette.responses import StreamingResponse, FileResponse
from pathlib import Path
import os
import mimetypes
import re
import asyncio

router = APIRouter()


async def async_file_iterator(path, start=0, length=None, chunk_size=4 * 1024 * 1024):
    with open(path, "rb") as f:
        f.seek(start)
        remaining = length
        while True:
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
    base_path = Path(os.getenv("DOWNLOAD_PATH", "/downloads")).resolve()
    abs_path = (base_path / path).resolve()

    if not abs_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if not abs_path.is_file():
        raise HTTPException(status_code=400, detail="Not a file")
    if not str(abs_path).startswith(str(base_path)):
        raise HTTPException(status_code=403, detail="Access denied")

    if download:
        return FileResponse(abs_path, filename=abs_path.name)

    file_size = abs_path.stat().st_size
    range_header = request.headers.get("Range")

    mimetype = mimetypes.guess_type(abs_path)[0] or "application/octet-stream"
    if mimetype.startswith("video"):
        mimetype = "video/mp4"

    # --------------------
    # NO RANGE -> FileResponse (zero RAM)
    # --------------------
    if not range_header:
        return FileResponse(
            abs_path,
            media_type=mimetype,
            headers={"Accept-Ranges": "bytes"},
        )

    # --------------------
    # RANGE REQUEST
    # --------------------
    match = re.match(r"bytes=(\d+)-(\d*)", range_header)
    if not match:
        raise HTTPException(status_code=416, detail="Invalid range")

    start = int(match.group(1))
    end = int(match.group(2)) if match.group(2) else file_size - 1

    if start >= file_size:
        raise HTTPException(status_code=416, detail="Range not satisfiable")

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
    user_id = authenticate_user(request.cookies.get("session_token"))
    return handle_stream_file(request, path, download)
