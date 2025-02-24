import re
import os
import json
from fastapi import APIRouter, HTTPException, Request
from ..auth.common import authenticate_user
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from shared.factory import redis



router = APIRouter()


class FileItem(BaseModel):
    name: str
    last_modified: datetime
    is_directory: bool
    size: Optional[int]  # Size for files, None for directories
    is_transcoding: bool = False

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


@router.get("/browse", response_model=List[FileItem])
async def browse_directory(path: str, request: Request):
    user_id = authenticate_user(request.cookies.get("session_token"))
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
        for item in abs_path.iterdir():
            if item.is_dir():
                # Calculate the size of the directory
                dir_size = sum(
                    
                    f.stat().st_size for f in item.glob("**/*") if f.is_file()
                )
            else:
                dir_size = None  # Size is only relevant for files

            #TODO: Verify video file
            transcode_in_progress = False

            if item.is_file() and is_transcoded_file(item.name) and redis.get(f"transcoding_progress/{abs_path}/{item.name}"):
                transcode_in_progress = True


            files.append(
                FileItem(
                    name=item.name,
                    last_modified=datetime.fromtimestamp(item.stat().st_mtime),
                    is_directory=item.is_dir(),
                    size=dir_size if item.is_dir() else item.stat().st_size,
                    is_transcoding=transcode_in_progress
                )
            )

        # Sort files: directories first, then by name
        return sorted(files, key=lambda x: (not x.is_directory, x.name.lower()))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
