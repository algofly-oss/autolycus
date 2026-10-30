from fastapi import APIRouter, Request, Response, HTTPException
from shared.factory import db, redis
from .common import UserSigninDto, get_session_token
from .session_utils import create_session_record
from shared.modules.auth_session import SESSION_SECONDS, set_session_cookie
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

    # Check if user exists
    existing_user = await db.users.find_one({"username": user.username})

    if not existing_user:
        raise HTTPException(status_code=400, detail="incorrect username")

    # Check if password is correct
    if bcrypt.checkpw(user.password.encode("utf-8"), existing_user["password"]):
        # create a new session token
        user_id = str(existing_user.get("_id"))
        existing_session_token = get_session_token(request, "")
        existing_user_id = getattr(request.state, "session_user_id", None)
        session_token = (existing_session_token if existing_user_id == user_id.encode()
                         else str(uuid.uuid4()))
        redis.set(session_token, user_id, ex=SESSION_SECONDS)
        await create_session_record(db, user_id, session_token, request)
        set_session_cookie(response, request, session_token)
        return {"msg": "success"}

    raise HTTPException(status_code=400, detail="incorrect password")
