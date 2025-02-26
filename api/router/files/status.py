from fastapi import APIRouter, HTTPException, Request
from ..auth.common import authenticate_user
from pathlib import Path
import shutil
import traceback
import os
from shared.sockets import emit

router = APIRouter()


def get_disk_usage(user_id):
    try:
        total = shutil.disk_usage("/downloads").total
        occupied_by_user = 0
        if os.path.exists(f"/downloads/{user_id}"):
            occupied_by_user = sum(
                f.stat().st_blocks * 512
                for f in Path(f"/downloads/{user_id}").rglob("*")
                if f.is_file()
            )
        occupied_by_others = shutil.disk_usage("/downloads").used - occupied_by_user

        return {"used": occupied_by_user, "total": total - occupied_by_others}
    except Exception as e:
        traceback.print_exc()
        return {"used": 0, total: 0}


@router.get("/status")
async def disk_usage_status(request: Request):
    user_id = authenticate_user(request.cookies.get("session_token")).decode()
    disk_usage = get_disk_usage(str(user_id))
    # emit(f"/stc/disk-usage", disk_usage, user_id)
    return disk_usage
