from fastapi import APIRouter, HTTPException, Request
from ..auth.common import authenticate_user
from pathlib import Path
from pydantic import BaseModel
import os
import shutil
from zipfile import ZipFile
from .status import get_disk_usage
from shared.sockets import emit


router = APIRouter()


class ArchiveResponse(BaseModel):
    archive_path: str


@router.post("/archive")
async def archive_directory(path: str, request: Request):
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

        # Archive the directory
        # archive_name = abs_path.parent / f"{abs_path.name}"
        # archive_path = shutil.make_archive(base_name=archive_name ,base_dir=abs_path, format='zip', root_dir=abs_path)

        archive_name = abs_path.parent / f"{abs_path.name}.zip"
        with ZipFile(str(archive_name), "w") as zipf:
            for root, dirs, files in os.walk(abs_path):
                for file in files:
                    zipf.write(
                        os.path.join(root, file),
                        os.path.relpath(os.path.join(root, file), abs_path),
                    )

        emit(f"/stc/disk-usage", get_disk_usage(user_id.decode()), user_id.decode())
        return archive_name

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
