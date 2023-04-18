from fastapi import HTTPException
from shared.factory import redis
from pydantic import BaseModel


class UserSignupDto(BaseModel):
    name: str
    username: str
    password: str


class UserSigninDto(BaseModel):
    username: str
    password: str


def authenticate_user(session_token):
    login_error = HTTPException(status_code=400, detail="User not logged in")
    # Check if session token exists
    if not session_token:
        raise login_error

    # Check if session token is valid
    user_id = redis.get(session_token)
    if not user_id:
        raise login_error

    return user_id
