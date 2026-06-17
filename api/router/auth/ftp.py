import datetime
import os
import re
from pathlib import Path
from urllib.parse import quote

import bcrypt
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from shared.env import FTP_HOOK_SECRET, FTP_PUBLIC_HOST, FTP_PUBLIC_PORT
from shared.factory import db

from .common import authenticate_user
from .preferences_utils import serialize_preferences

router = APIRouter()

FTP_USERNAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{2,63}$")


class FtpSettingsUpdate(BaseModel):
    enabled: bool = False
    username: str = ""
    password: str = ""


class FtpHookPayload(BaseModel):
    username: str = ""
    password: str = ""
    protocol: str = ""
    ip: str = ""


def _user_object_id(request: Request):
    user_id = authenticate_user(request)
    if isinstance(user_id, bytes):
        user_id = user_id.decode("utf-8")
    return ObjectId(str(user_id))


def _public_host(request: Request):
    configured_host = str(FTP_PUBLIC_HOST or "").strip()
    if configured_host:
        return configured_host

    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    host = str(forwarded_host or "").split(",")[0].strip()
    if ":" in host:
        host = host.split(":", 1)[0]
    return host or "localhost"


def _ftp_url(request: Request, username: str):
    if not username:
        return ""

    port = str(FTP_PUBLIC_PORT or "2121").strip()
    host = _public_host(request)
    port_suffix = "" if port == "21" else f":{port}"
    return f"ftp://{quote(username)}@{host}{port_suffix}"


def _serialize_ftp_settings(request: Request, preferences):
    serialized = serialize_preferences(preferences)
    ftp = dict(serialized.get("ftp") or {})
    if ftp.get("username"):
        ftp["url"] = _ftp_url(request, ftp["username"])
    serialized["ftp"] = ftp
    return serialized


@router.get("/ftp")
async def get_ftp_settings(request: Request):
    user_object_id = _user_object_id(request)
    user = await db.users.find_one({"_id": user_object_id}, {"preferences": 1})
    if not user:
        raise HTTPException(status_code=400, detail="User not logged in")

    preferences = user.get("preferences") or {}
    return {"ftp": _serialize_ftp_settings(request, preferences).get("ftp") or {}}


@router.patch("/ftp")
async def update_ftp_settings(settings: FtpSettingsUpdate, request: Request):
    user_object_id = _user_object_id(request)
    user = await db.users.find_one({"_id": user_object_id}, {"preferences": 1})
    if not user:
        raise HTTPException(status_code=400, detail="User not logged in")

    current_ftp = dict((user.get("preferences") or {}).get("ftp") or {})
    username = str(settings.username or "").strip()
    password = str(settings.password or "")

    if settings.enabled:
        if not FTP_USERNAME_RE.fullmatch(username):
            raise HTTPException(
                status_code=400,
                detail="FTP username must be 3-64 characters using letters, numbers, dots, dashes, or underscores.",
            )

        existing_user = await db.users.find_one(
            {
                "_id": {"$ne": user_object_id},
                "preferences.ftp.username": username,
            },
            {"_id": 1},
        )
        if existing_user:
            raise HTTPException(status_code=400, detail="FTP username is already in use")

        if not current_ftp.get("password_hash") and not password:
            raise HTTPException(status_code=400, detail="FTP password is required")
        if password and len(password) < 8:
            raise HTTPException(
                status_code=400,
                detail="FTP password must be at least 8 characters",
            )

    updates = {
        "preferences.ftp.enabled": bool(settings.enabled),
        "preferences.ftp.username": username,
        "preferences.ftp.updated_at": datetime.datetime.utcnow(),
        "preferences.updated_at": datetime.datetime.utcnow(),
    }

    if password:
        salt = bcrypt.gensalt()
        updates["preferences.ftp.password_hash"] = bcrypt.hashpw(
            password.encode("utf-8"),
            salt,
        )

    await db.users.update_one({"_id": user_object_id}, {"$set": updates})
    updated_user = await db.users.find_one({"_id": user_object_id}, {"preferences": 1})
    preferences = updated_user.get("preferences") or {}
    serialized = _serialize_ftp_settings(request, preferences)

    return {
        "ftp": serialized.get("ftp") or {},
        "preferences": serialized,
    }


@router.post("/ftp/hook")
async def ftp_auth_hook(payload: FtpHookPayload, request: Request):
    secret = request.query_params.get("secret", "")
    if not FTP_HOOK_SECRET or secret != FTP_HOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid hook secret")

    protocol = str(payload.protocol or "").upper()
    if protocol and protocol != "FTP":
        raise HTTPException(status_code=403, detail="Unsupported protocol")

    username = str(payload.username or "").strip()
    password = str(payload.password or "")
    user = await db.users.find_one(
        {
            "preferences.ftp.enabled": True,
            "preferences.ftp.username": username,
        },
        {"preferences": 1},
    )

    ftp = dict((user or {}).get("preferences", {}).get("ftp") or {})
    password_hash = ftp.get("password_hash")
    if not user or not password_hash:
        raise HTTPException(status_code=403, detail="Invalid FTP credentials")

    if not bcrypt.checkpw(password.encode("utf-8"), password_hash):
        raise HTTPException(status_code=403, detail="Invalid FTP credentials")

    user_id = str(user["_id"])
    home_dir = Path(os.getenv("DOWNLOAD_PATH", "/downloads")) / user_id
    home_dir.mkdir(parents=True, exist_ok=True)

    return {
        "status": 1,
        "username": username,
        "expiration_date": 0,
        "home_dir": str(home_dir),
        "uid": 0,
        "gid": 0,
        "max_sessions": 0,
        "quota_size": 0,
        "quota_files": 0,
        "permissions": {"/": ["*"]},
        "upload_bandwidth": 0,
        "download_bandwidth": 0,
        "filters": {"allowed_ip": [], "denied_ip": []},
        "public_keys": [],
        "ftp_security": 0,
        "external_auth_cache_time": 0,
    }
