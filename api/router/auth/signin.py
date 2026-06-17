from fastapi import APIRouter, Request, Response, HTTPException
from shared.factory import db, redis
from shared.env import SESSION_COOKIE_NAME
from .common import UserSigninDto, get_session_token
from .session_utils import create_session_record, touch_session_record
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
    existing_session_token = get_session_token(request, "")
    existing_user_id = redis.get(existing_session_token)
    if existing_user_id:
        await touch_session_record(db, existing_session_token, request)
        return {"msg": "success"}

    # Check if user exists
    existing_user = await db.users.find_one({"username": user.username})

    if not existing_user:
        raise HTTPException(status_code=400, detail="incorrect username")

    # Check if password is correct
    if bcrypt.checkpw(user.password.encode("utf-8"), existing_user["password"]):
        # create a new session token
        session_token = str(uuid.uuid4())
        user_id = str(existing_user.get("_id"))
        redis.set(session_token, user_id)
        await create_session_record(db, user_id, session_token, request)
        response.set_cookie(
            key=SESSION_COOKIE_NAME, value=session_token, httponly=True
        )
        return {"msg": "success"}

    raise HTTPException(status_code=400, detail="incorrect password")
