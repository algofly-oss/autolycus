from fastapi import APIRouter, Request
from ..auth.common import authenticate_user
from shared.modules.storage_usage import get_disk_usage

router = APIRouter()


@router.get("/status")
async def disk_usage_status(request: Request):
    authenticate_user(request)
    return get_disk_usage()
