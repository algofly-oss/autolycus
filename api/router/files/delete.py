from fastapi import APIRouter, HTTPException, Request
from ..auth.common import authenticate_user
from pathlib import Path
import os
import shutil
from .status import get_disk_usage
from shared.sockets import emit
from shared.factory import db

router = APIRouter()


def delete_dir(abs_path: Path):
    shutil.rmtree(abs_path)


@router.delete("/delete")
async def delete_file(path: str, request: Request):
    user_id = authenticate_user(request.cookies.get("session_token"))
    try:
        info_hash = path.split("/")[1]
        full_path = os.path.join(os.getenv("DOWNLOAD_PATH", "/downloads"), path)
        public_url = await db.public_urls.find_one(
            {
                "info_hash": info_hash,
                "path": full_path,
            }
        )
        if public_url:
            # delete public url if exists
            await db.public_urls.delete_one(
                {
                    "info_hash": info_hash,
                    "path": full_path,
                }
            )

        # Convert the relative path to absolute path
        base_path = Path(os.getenv("DOWNLOAD_PATH", "/downloads"))
        abs_path = base_path / path

        # Ensure the path exists
        if not abs_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        # Ensure the path is within the base directory
        if not str(abs_path.resolve()).startswith(str(base_path.resolve())):
            raise HTTPException(status_code=403, detail="Access denied")

        # Delete the file or directory
        if abs_path.is_file():
            abs_path.unlink()
        elif abs_path.is_dir():
            delete_dir(abs_path)

        emit(f"/stc/disk-usage", get_disk_usage(user_id.decode()), user_id.decode())
        return {"status": "success", "message": "File deleted successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
