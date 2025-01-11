from fastapi import APIRouter, HTTPException, Request
from ..auth.common import authenticate_user
from pathlib import Path
import os
import logging

router = APIRouter()

@router.post("/rename")
async def rename_item(source_path: str, new_name: str, request: Request):
    user_id = authenticate_user(request.cookies.get("session_token"))
    try:
        base_path = Path(os.getenv("DOWNLOAD_PATH", "/downloads"))
        abs_source_path = base_path / source_path
        abs_new_path = abs_source_path.parent / new_name

        # Ensure the source path exists
        if not abs_source_path.exists():
            logging.error(f"Source path not found: {abs_source_path}")
            raise HTTPException(status_code=404, detail="Source not found")

        # Ensure the new path does not already exist
        if abs_new_path.exists():
            logging.error(f"Destination path already exists: {abs_new_path}")
            raise HTTPException(status_code=400, detail="Destination already exists")

        # Ensure the paths are within the base directory
        if not str(abs_source_path.resolve()).startswith(str(base_path.resolve())) or \
           not str(abs_new_path.resolve()).startswith(str(base_path.resolve())):
            logging.error(f"Access denied for paths: {abs_source_path}, {abs_new_path}")
            raise HTTPException(status_code=403, detail="Access denied")

        # Rename the file or directory
        abs_source_path.rename(abs_new_path)

        return {"detail": "Item renamed successfully"}

    except Exception as e:
        logging.error(f"Error renaming item: {e}")
        raise HTTPException(status_code=500, detail=str(e))
