import os
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status

from ..auth.common import authenticate_user
from tasks.delete_path import delete_path


router = APIRouter()


def delete_dir(abs_path: Path):
    """Compatibility helper used by the separate torrent-delete endpoint."""
    shutil.rmtree(abs_path)


def _within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


@router.delete("/delete", status_code=status.HTTP_202_ACCEPTED)
async def delete_file(path: str, request: Request):
    user_id = authenticate_user(request).decode()
    download_root = Path(os.getenv("DOWNLOAD_PATH", "/downloads")).resolve()
    user_root = (download_root / user_id).resolve()
    target = (download_root / path.lstrip("/")).resolve()

    if not _within(target, user_root):
        raise HTTPException(status_code=403, detail="Access denied")
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")

    result = delete_path.delay(path, user_id)
    return {"status": "queued", "task_id": result.task_id}
