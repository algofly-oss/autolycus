from fastapi import APIRouter, Request, Response, HTTPException
from shared.factory import redis

router = APIRouter()


@router.post("/signout")
async def signout(request: Request, response: Response):
    session_token = request.cookies.get("session_token")
    if not session_token:
        return {"msg": "user not logged in"}

    redis.delete(session_token)
    response.delete_cookie(key="session_token")

    return {"msg": "success"}
