from fastapi import APIRouter, HTTPException, Request
from ..auth.common import authenticate_user
from pathlib import Path
import shutil
import os
from .status import get_disk_usage
from shared.sockets import emit

router = APIRouter()

@router.post("/copy")
async def copy_file(source_path: str, destination_path: str, is_directory: bool, request: Request):
    user_id = authenticate_user(request.cookies.get("session_token"))
    try:
        base_path = Path(os.getenv("DOWNLOAD_PATH", "/downloads"))
        abs_source_path = base_path / source_path
        abs_destination_path = base_path / destination_path

        # Ensure the source path exists
        if not abs_source_path.exists():
            raise HTTPException(status_code=404, detail="Source not found")

        # Ensure the destination directory exists
        if not abs_destination_path.parent.exists():
            raise HTTPException(status_code=404, detail="Destination directory not found")

        # Ensure the paths are within the base directory
        if not str(abs_source_path.resolve()).startswith(str(base_path.resolve())) or \
           not str(abs_destination_path.resolve()).startswith(str(base_path.resolve())):
            raise HTTPException(status_code=403, detail="Access denied")

        # Copy the file or directory
        if is_directory:
            if not abs_source_path.is_dir():
                raise HTTPException(status_code=400, detail="Source is not a directory")
            shutil.copytree(abs_source_path, abs_destination_path)
        else:
            if not abs_source_path.is_file():
                raise HTTPException(status_code=400, detail="Source is not a file")
            shutil.copy2(abs_source_path, abs_destination_path)

        emit(f"/stc/disk-usage", get_disk_usage(user_id.decode()), user_id.decode())
        return {"detail": "Item copied successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
