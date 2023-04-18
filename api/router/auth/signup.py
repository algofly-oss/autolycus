from fastapi import APIRouter, Response, HTTPException
from shared.factory import db, redis
from .common import UserSignupDto
import datetime
import bcrypt
import uuid


router = APIRouter()


@router.post("/signup")
async def signup(user: UserSignupDto, response: Response):
    """
    Create a new user.


    **Parameters**:
    - `name` (str): The name of the user.
    - `username` (str): The email/phone of the user.
    - `password` (str): The password of the user.

    **Returns**:
    - `msg` (str): The message of the response.
    """

    # Check if user already exists
    if await db.users.find_one({"username": user.username}):
        raise HTTPException(status_code=400, detail="User already exists")

    # Create a new user
    salt = bcrypt.gensalt()
    await db.users.insert_one(
        {
            "name": user.name,
            "username": user.username,
            "password": bcrypt.hashpw(user.password.encode("utf-8"), salt),
            "role": "user",
            "salt": salt,
            "created_at": datetime.datetime.utcnow(),
        }
    )

    # find the created user_id
    user = await db.users.find_one({"username": user.username})
    user_id = str(user.get("_id"))

    # create a new session token
    session_token = str(uuid.uuid4())
    redis.set(session_token, user_id)
    response.set_cookie(key="session_token", value=session_token, httponly=True)

    return {"msg": "user created"}
