from fastapi import HTTPException, Request
from shared.factory import redis
from shared.env import SESSION_COOKIE_NAME
from pydantic import BaseModel


class UserSignupDto(BaseModel):
    name: str
    username: str
    password: str


class UserSigninDto(BaseModel):
    username: str
    password: str


def get_session_token(request: Request, default=None):
    return request.cookies.get(SESSION_COOKIE_NAME, default)


def authenticate_user(request: Request):
    login_error = HTTPException(status_code=400, detail="User not logged in")
    session_token = get_session_token(request)

    # Check if session token exists
    if not session_token:
        raise login_error

    # Check if session token is valid
    user_id = redis.get(session_token)
    if not user_id:
        raise login_error

    return user_id
