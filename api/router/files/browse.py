import re
import os
import json
from fastapi import APIRouter, HTTPException, Request
from ..auth.common import authenticate_user
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from bson import ObjectId
from shared.factory import db, redis
from .public_url import ensure_public_url_record



router = APIRouter()


class FileItem(BaseModel):
    name: str
    last_modified: datetime
    is_directory: bool
    size: Optional[int]  # Size for files, None for directories
    total_size: Optional[int] = None
    is_partial: bool = False
    is_transcoding: bool = False
    public_url_key: Optional[str] = None

def is_transcoded_file(filename):  
    # Regular expression pattern to match resolution part (e.g., _360)  
    pattern = r'_(\d{3,4})(?=p.mp4$)'  
    
    # Search for the pattern in the filename  
    match = re.search(pattern, filename)  
    
    # If a match is found, return True and the matched part  
    if match:  
        return True
    
    # If no match is found, return False and None  
    return False  


def allocated_size(path: Path):
    try:
        stat = path.stat()
        return min(stat.st_blocks * 512, stat.st_size)
    except AttributeError:
        return path.stat().st_size


def path_display_sizes(path: Path, use_allocated_size=False):
    total_size = path.stat().st_size
    current_size = allocated_size(path) if use_allocated_size else total_size
    return current_size, total_size


def tree_display_sizes(path: Path, use_allocated_size=False):
    current_total = 0
    total = 0
    for item in path.glob("**/*"):
        if item.is_file():
            current_size, total_size = path_display_sizes(item, use_allocated_size)
            current_total += current_size
            total += total_size
    return current_total, total


async def is_unfinished_torrent_path(path: str, user_id: str):
    relative_parts = Path(path).parts
    if len(relative_parts) < 2 or relative_parts[0] != str(user_id):
        return False

    torrent_id = relative_parts[1]
    try:
        user_oid = ObjectId(str(user_id))
    except Exception:
        return False

    torrent = await db.torrents.find_one(
        {
            "user_id": user_oid,
            "$or": [{"info_hash": torrent_id}, {"url_hash": torrent_id}],
        },
        {"is_finished": True},
    )
    return bool(torrent and not torrent.get("is_finished"))


@router.get("/browse", response_model=List[FileItem])
async def browse_directory(path: str, request: Request):
    user_id = authenticate_user(request).decode("utf-8")
    try:
        # Convert the relative path to absolute path
        base_path = Path(os.getenv("DOWNLOAD_PATH", "/downloads"))
        abs_path = base_path / path

        # Ensure the path exists and is a directory
        if not abs_path.exists():
            raise HTTPException(status_code=404, detail="Directory not found")
        if not abs_path.is_dir():
            raise HTTPException(status_code=400, detail="Not a directory")

        # Ensure the path is within the base directory
        if not str(abs_path.resolve()).startswith(str(base_path.resolve())):
            raise HTTPException(status_code=403, detail="Access denied")

        # List directory contents
        files = []
        use_allocated_size = await is_unfinished_torrent_path(path, user_id)
        path_parts = Path(path).parts
        torrent_id = path_parts[1] if len(path_parts) >= 2 else None
        for item in abs_path.iterdir():
            if item.is_dir():
                current_size, total_size = tree_display_sizes(item, use_allocated_size)
            else:
                current_size, total_size = path_display_sizes(item, use_allocated_size)

            #TODO: Verify video file
            transcode_in_progress = False

            if item.is_file() and is_transcoded_file(item.name) and redis.get(f"transcoding_progress/{abs_path}/{item.name}"):
                transcode_in_progress = True

            public_url_key = None
            if item.is_file() and torrent_id:
                public_url_key = await ensure_public_url_record(
                    user_id,
                    torrent_id,
                    str(item),
                    active=False,
                )

            files.append(
                FileItem(
                    name=item.name,
                    last_modified=datetime.fromtimestamp(item.stat().st_mtime),
                    is_directory=item.is_dir(),
                    size=current_size,
                    total_size=total_size,
                    is_partial=use_allocated_size and current_size < total_size,
                    is_transcoding=transcode_in_progress,
                    public_url_key=public_url_key,
                )
            )

        # Sort files: directories first, then by name
        return sorted(files, key=lambda x: (not x.is_directory, x.name.lower()))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
