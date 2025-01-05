from fastapi import APIRouter, HTTPException, Request
from ..auth.common import authenticate_user
from fastapi.responses import FileResponse
from starlette.responses import Response as StreamingResponse
from pathlib import Path
import os
import mimetypes
import re
import contextlib
import mmap

router = APIRouter()


def get_chunk(full_path, byte1=None, byte2=None):
    file_size = os.stat(full_path).st_size
    start = 0
    length = 1024

    if byte1 < file_size:
        start = byte1
    if byte2:
        length = byte2 + 1 - byte1
    else:
        length = file_size - start

    with open(full_path, "rb") as f:
        with contextlib.closing(
            mmap.mmap(f.fileno(), length=0, access=mmap.ACCESS_READ)
        ) as m:
            m.seek(start)
            chunk = m.read(length)
            m.flush()

    return chunk, start, length, file_size


@router.get("/stream")
async def stream_file(request: Request, path: str = "", download: bool = False):
    user_id = authenticate_user(request.cookies.get("session_token"))
    try:
        # Convert the relative path to absolute path
        base_path = Path(os.getenv("DOWNLOAD_PATH", "/downloads"))
        abs_path = base_path / path

        # Ensure the path exists and is a file
        if not abs_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        if not abs_path.is_file():
            raise HTTPException(status_code=400, detail="Not a file")

        # Ensure the path is within the base directory
        if not str(abs_path.resolve()).startswith(str(base_path.resolve())):
            raise HTTPException(status_code=403, detail="Access denied")

        if download:
            return FileResponse(
                path=abs_path,
                media_type="application/octet-stream",
                filename=os.path.basename(abs_path),
                headers={
                    "Content-Disposition": f"attachment; filename={os.path.basename(abs_path)}"
                },
            )

        # Handle byte range requests
        range_header = request.headers.get("Range", None)
        byte1, byte2 = 0, None
        if range_header:
            match = re.search(r"(\d+)-(\d*)", range_header)
            groups = match.groups()

            if groups[0]:
                byte1 = int(groups[0])
            if groups[1]:
                byte2 = int(groups[1])

        try:
            mimetype = mimetypes.guess_type(abs_path)[0]
            if mimetype is None:
                mimetype = "text/plain"
            elif mimetype.startswith("video"):
                mimetype = "video/mp4"
        except:
            return FileResponse(
                path=path,
                media_type="application/octet-stream",
                filename=os.path.basename(abs_path),
                headers={
                    "Content-Disposition": f"attachment; filename={os.path.basename(abs_path)}"
                },
            )

        chunk, start, length, file_size = get_chunk(abs_path, byte1, byte2)
        headers = {
            "Content-Range": f"bytes {start}-{start + length - 1}/{file_size}",
            "Accept-Ranges": "bytes",
        }

        return StreamingResponse(
            chunk, status_code=206, headers=headers, media_type=mimetype
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
