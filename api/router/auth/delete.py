from fastapi import APIRouter, Request, Response, HTTPException
from shared.factory import db, redis
from shared.env import SESSION_COOKIE_NAME
import bcrypt
from bson import ObjectId
from .common import UserSigninDto, get_session_token

router = APIRouter()


@router.delete("/delete")
async def delete_account(user: UserSigninDto, request: Request, response: Response):
    # Check if user exists
    username = await db.users.find_one({"username": user.username})

    if not username:
        raise HTTPException(status_code=400, detail="Username does not exist")

    # Check if password is correct
    if bcrypt.checkpw(user.password.encode("utf-8"), username["password"]):
        # delete user from db
        await db.users.delete_one({"_id": ObjectId(username.get("_id"))})

        # delete session token
        session_token = get_session_token(request, "")
        redis.delete(session_token)
        response.delete_cookie(key=SESSION_COOKIE_NAME)

        return {"msg": "user deleted"}

    raise HTTPException(status_code=400, detail="Password is incorrect")
