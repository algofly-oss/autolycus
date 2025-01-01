from fastapi import APIRouter, HTTPException
from pathlib import Path
import os
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter()

class FileItem(BaseModel):
    name: str
    last_modified: datetime
    is_directory: bool
    size: Optional[int]

@router.get("/browse", response_model=List[FileItem])
async def browse_directory(path: str = ""):
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
            files.append(FileItem(
                name=item.name,
                last_modified=datetime.fromtimestamp(item.stat().st_mtime),
                is_directory=item.is_dir(),
                size=item.stat().st_size if item.is_file() else None
            ))

        print("files", files)
        
        # Sort files: directories first, then by name
        return sorted(
            files,
            key=lambda x: (not x.is_directory, x.name.lower())
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
