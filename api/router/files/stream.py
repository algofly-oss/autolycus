from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pathlib import Path
import os
from typing import BinaryIO
import mimetypes

router = APIRouter()

def file_iterator(file_obj: BinaryIO, chunk_size: int = 1024 * 1024) -> bytes:
    """Stream file in chunks to prevent memory overload"""
    while True:
        chunk = file_obj.read(chunk_size)
        if not chunk:
            break
        yield chunk

def get_content_type(file_path: Path) -> str:
    """Get the content type based on file extension"""
    content_type, _ = mimetypes.guess_type(str(file_path))
    if not content_type:
        if file_path.suffix.lower() in ['.mkv', '.webm']:
            return "video/webm"
        elif file_path.suffix.lower() in ['.avi']:
            return "video/x-msvideo"
        return "application/octet-stream"
    return content_type

@router.get("/stream")
async def stream_file(path: str = "", download: bool = False):
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
        
        # Open file in binary mode
        file = open(abs_path, mode="rb")
        
        # Get file size for Content-Length header
        file_size = abs_path.stat().st_size
        
        # Get content type
        content_type = get_content_type(abs_path)
        
        headers = {
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes"
        }
        
        # If download is requested, add Content-Disposition header
        if download:
            headers["Content-Disposition"] = f'attachment; filename="{abs_path.name}"'
        
        # Return streaming response
        return StreamingResponse(
            file_iterator(file),
            media_type=content_type,
            headers=headers
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 