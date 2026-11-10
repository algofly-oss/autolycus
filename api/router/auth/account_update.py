import base64
import datetime
import re
from typing import Optional

import bcrypt
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, constr
from pymongo.errors import DuplicateKeyError

from shared.factory import db

from .common import authenticate_user
from .preferences_utils import serialize_preferences

router = APIRouter()

MAX_PROFILE_PICTURE_BYTES = 2 * 1024 * 1024
ALLOWED_PROFILE_PICTURE_TYPES = {"image/png", "image/jpeg", "image/webp"}
DATA_URL_RE = re.compile(
    r"^data:(?P<content_type>[-\w.]+/[-\w.+]+);base64,(?P<data>.+)$"
)
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class ProfilePicturePayload(BaseModel):
    data_url: str
    filename: Optional[str] = None
    content_type: Optional[str] = None
    size: Optional[int] = None


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    current_password: Optional[str] = None
    profile_picture: Optional[ProfilePicturePayload] = None
    remove_profile_picture: bool = False


class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str


class SubtitlePreferences(BaseModel):
    enabled: bool = False
    language: constr(regex=r"^[a-z]{2,3}$") = "en"
    auto_match: bool = True


class PreferencesUpdate(BaseModel):
    home_view_mode: Optional[str] = None
    search_view_mode: Optional[str] = None
    video_quality: Optional[str] = None
    video_subtitles: Optional[SubtitlePreferences] = None
    video_audio_language: Optional[str] = None


def _user_object_id(request: Request):
    user_id = authenticate_user(request)
    if isinstance(user_id, bytes):
        user_id = user_id.decode("utf-8")
    return ObjectId(str(user_id))


def _serialize_user(user):
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


def _normalize_profile_picture(payload: ProfilePicturePayload):
    data_url = str(payload.data_url or "").strip()
    match = DATA_URL_RE.match(data_url)
    if not match:
        raise HTTPException(status_code=400, detail="Profile picture must be an image")

    content_type = match.group("content_type").lower()
    if content_type == "image/jpg":
        content_type = "image/jpeg"

    if content_type not in ALLOWED_PROFILE_PICTURE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Profile picture must be a PNG, JPG, or WebP image",
        )

    try:
        image_bytes = base64.b64decode(match.group("data"), validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="Profile picture could not be read")

    if not image_bytes:
        raise HTTPException(status_code=400, detail="Profile picture is empty")

    if len(image_bytes) > MAX_PROFILE_PICTURE_BYTES:
        raise HTTPException(
            status_code=400,
            detail="Profile picture must be 2 MB or smaller",
        )

    return {
        "data_url": data_url,
        "content_type": content_type,
        "filename": str(payload.filename or "").strip()[:160],
        "size": len(image_bytes),
        "updated_at": datetime.datetime.utcnow(),
    }


@router.patch("/account")
async def update_account(account: AccountUpdate, request: Request):
    user_object_id = _user_object_id(request)
    user = await db.users.find_one({"_id": user_object_id})

    if not user:
        raise HTTPException(status_code=400, detail="User not logged in")

    updates = {}
    unset_updates = {}
    next_name = str(account.name or "").strip()
    next_email = str(account.email or "").strip().lower()
    current_email = str(user.get("email") or user.get("username") or "").lower()

    if next_name and next_name != user.get("name"):
        updates["name"] = next_name

    email_changed = bool(next_email and next_email != current_email)
    if email_changed:
        if not EMAIL_RE.fullmatch(next_email):
            raise HTTPException(status_code=400, detail="Enter a valid email address")
        if not account.current_password:
            raise HTTPException(status_code=400, detail="Current password required")
        if not bcrypt.checkpw(account.current_password.encode("utf-8"), user["password"]):
            raise HTTPException(status_code=400, detail="Incorrect password")

        existing_user = await db.users.find_one(
            {
                "_id": {"$ne": user_object_id},
                "$or": [{"username": next_email}, {"email": next_email}],
            },
            {"_id": 1},
        )
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already exists")

        updates["username"] = next_email
        updates["email"] = next_email

    if account.profile_picture is not None:
        updates["profile_picture"] = _normalize_profile_picture(account.profile_picture)
    elif account.remove_profile_picture:
        unset_updates["profile_picture"] = ""

    if updates or unset_updates:
        operation = {}
        if updates:
            operation["$set"] = updates
        if unset_updates:
            operation["$unset"] = unset_updates
        try:
            await db.users.update_one({"_id": user_object_id}, operation)
        except DuplicateKeyError:
            raise HTTPException(status_code=400, detail="Email already exists")

    updated_user = await db.users.find_one({"_id": user_object_id})
    return _serialize_user(updated_user)


@router.patch("/preferences")
async def update_preferences(preferences: PreferencesUpdate, request: Request):
    user_object_id = _user_object_id(request)
    user = await db.users.find_one({"_id": user_object_id}, {"_id": 1})

    if not user:
        raise HTTPException(status_code=400, detail="User not logged in")

    updates = {}
    if preferences.home_view_mode is not None:
        if preferences.home_view_mode not in {"list", "grid"}:
            raise HTTPException(status_code=400, detail="Invalid home view mode")
        updates["preferences.home_view_mode"] = preferences.home_view_mode

    if preferences.search_view_mode is not None:
        if preferences.search_view_mode not in {"list", "grid"}:
            raise HTTPException(status_code=400, detail="Invalid search view mode")
        updates["preferences.search_view_mode"] = preferences.search_view_mode

    if preferences.video_quality is not None:
        if preferences.video_quality not in {"auto", "original", "144p", "240p", "360p", "480p", "720p", "1080p", "1440p", "2160p"}:
            raise HTTPException(status_code=400, detail="Invalid video quality")
        updates["preferences.video_quality"] = preferences.video_quality

    if preferences.video_subtitles is not None:
        updates["preferences.video_subtitles"] = preferences.video_subtitles.dict()
    if preferences.video_audio_language is not None:
        if not __import__("re").fullmatch(r"[a-z]{2,3}",preferences.video_audio_language):
            raise HTTPException(400,"Invalid audio language")
        updates["preferences.video_audio_language"] = preferences.video_audio_language

    from shared.modules.media_profiles import profile_id
    selected=await profile_id(request,str(user_object_id))
    if updates:
        if selected == "default":
            await db.users.update_one({"_id":user_object_id},{"$set":{**updates,"preferences.updated_at":datetime.datetime.utcnow()}})
        await db.media_profiles.update_one({"_id":f"{user_object_id}:{selected}"},{"$set":updates})

    updated_user = await db.users.find_one({"_id": user_object_id})
    profile=await db.media_profiles.find_one({"_id":f"{user_object_id}:{selected}"})
    merged={**(updated_user.get("preferences") or {}),**((profile or {}).get("preferences") or {})}
    return {"preferences": serialize_preferences(merged)}


@router.patch("/password")
async def update_password(password: PasswordUpdate, request: Request):
    user_object_id = _user_object_id(request)
    user = await db.users.find_one({"_id": user_object_id})

    if not user:
        raise HTTPException(status_code=400, detail="User not logged in")

    if not password.current_password:
        raise HTTPException(status_code=400, detail="Current password required")
    if not bcrypt.checkpw(password.current_password.encode("utf-8"), user["password"]):
        raise HTTPException(status_code=400, detail="Incorrect password")
    if len(password.new_password or "") < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters",
        )

    salt = bcrypt.gensalt()
    await db.users.update_one(
        {"_id": user_object_id},
        {
            "$set": {
                "password": bcrypt.hashpw(password.new_password.encode("utf-8"), salt),
                "salt": salt,
            }
        },
    )

    return {"msg": "success", "has_password": True}
