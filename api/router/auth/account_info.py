import datetime

from fastapi import APIRouter, Request, Response, HTTPException
from shared.factory import db, redis
from shared.env import SESSION_COOKIE_NAME
from bson import ObjectId
from pydantic import BaseModel
from .common import authenticate_user, get_session_token
from .session_utils import (
    create_session_record,
    is_public_ip,
    revoke_session_record,
    serialize_session,
    touch_session_record,
)
from .preferences_utils import serialize_preferences

router = APIRouter()


class SessionPublicIpUpdate(BaseModel):
    ip: str


@router.get("/me")
async def account_info(request: Request, response: Response):
    # Check if user is logged in
    user_id = authenticate_user(request)
    user_id_string = user_id.decode("utf-8") if isinstance(user_id, bytes) else str(user_id)
    session_token = get_session_token(request, "")
    if await touch_session_record(db, session_token, request) == 0:
        await create_session_record(db, user_id_string, session_token, request)

    user = await db.users.find_one({"_id": ObjectId(user_id_string)})

    if not user:
        raise HTTPException(status_code=400, detail="User not logged in")

    return {
        "name": user["name"],
        "username": user["username"],
        "email": user.get("email") or user["username"],
        "role": user["role"],
        "created_at": user["created_at"],
        "profile_picture": user.get("profile_picture"),
        "has_password": bool(user.get("password")),
        "preferences": serialize_preferences(user.get("preferences")),
    }


@router.get("/sessions")
async def list_sessions(request: Request):
    user_id = authenticate_user(request)
    user_id_string = user_id.decode("utf-8") if isinstance(user_id, bytes) else str(user_id)
    session_token = get_session_token(request, "")

    if await touch_session_record(db, session_token, request) == 0:
        await create_session_record(db, user_id_string, session_token, request)

    sessions = (
        await db.user_sessions.find(
            {
                "user_id": user_id_string,
                "revoked_at": None,
            }
        )
        .sort("last_accessed_at", -1)
        .to_list(length=100)
    )

    return {
        "data": [
            serialize_session(session, current_session_token=session_token)
            for session in sessions
        ]
    }


@router.patch("/sessions/current/ip")
async def update_current_session_ip(data: SessionPublicIpUpdate, request: Request):
    user_id = authenticate_user(request)
    user_id_string = user_id.decode("utf-8") if isinstance(user_id, bytes) else str(user_id)
    session_token = get_session_token(request, "")
    if not session_token:
        raise HTTPException(status_code=403, detail="Invalid session token")

    public_ip = str(data.ip or "").strip()
    if not is_public_ip(public_ip):
        raise HTTPException(status_code=400, detail="Invalid public IP address")

    if await touch_session_record(db, session_token, request) == 0:
        await create_session_record(db, user_id_string, session_token, request)

    result = await db.user_sessions.update_one(
        {
            "_id": session_token,
            "user_id": user_id_string,
            "revoked_at": None,
        },
        {
            "$set": {
                "ip": public_ip,
                "client_reported_ip": public_ip,
                "client_reported_ip_updated_at": datetime.datetime.utcnow(),
            }
        },
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"msg": "success", "ip": public_ip}


@router.delete("/sessions/{session_id}")
async def revoke_session(session_id: str, request: Request, response: Response):
    user_id = authenticate_user(request)
    user_id_string = user_id.decode("utf-8") if isinstance(user_id, bytes) else str(user_id)

    session = await db.user_sessions.find_one(
        {
            "_id": session_id,
            "user_id": user_id_string,
            "revoked_at": None,
        }
    )

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await revoke_session_record(db, redis, session_id)

    if session_id == get_session_token(request, ""):
        response.delete_cookie(key=SESSION_COOKIE_NAME)

    return {"msg": "success"}
