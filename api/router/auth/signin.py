from fastapi import APIRouter, Request, Response, HTTPException
from shared.factory import db, redis
from .common import UserSigninDto
import bcrypt
import uuid

router = APIRouter()


@router.post("/signin")
async def signin(user: UserSigninDto, request: Request, response: Response):
    """
    Sign in a user.


    **Parameters**:
    - `username` (str): The email/phone of the user.
    - `password` (str): The password of the user.

    **Returns**:
    - `msg` (str): The message of the response.
    """

    # Check if user is already logged in
    if redis.get(request.cookies.get("session_token", "")):
        return {"msg": "success"}

    # Check if user exists
    existing_user = await db.users.find_one({"username": user.username})

    if not existing_user:
        raise HTTPException(status_code=400, detail="incorrect username")

    # Check if password is correct
    if bcrypt.checkpw(user.password.encode("utf-8"), existing_user["password"]):
        # create a new session token
        session_token = str(uuid.uuid4())
        redis.set(session_token, str(existing_user.get("_id")))
        response.set_cookie(key="session_token", value=session_token, httponly=True)
        return {"msg": "success"}

    raise HTTPException(status_code=400, detail="incorrect password")
