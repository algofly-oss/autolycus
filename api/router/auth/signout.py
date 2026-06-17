from fastapi import APIRouter, Request, Response, HTTPException
from shared.factory import db, redis
from shared.env import SESSION_COOKIE_NAME
from .common import get_session_token
from .session_utils import revoke_session_record

router = APIRouter()


@router.post("/signout")
async def signout(request: Request, response: Response):
    session_token = get_session_token(request)
    if not session_token:
        return {"msg": "user not logged in"}

    await revoke_session_record(db, redis, session_token)
    response.delete_cookie(key=SESSION_COOKIE_NAME)

    return {"msg": "success"}
