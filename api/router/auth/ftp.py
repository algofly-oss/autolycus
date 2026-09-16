import datetime
import hashlib
import os
import re
import base64
import shutil
from pathlib import Path
from urllib.parse import quote

import bcrypt
from cryptography.fernet import Fernet, InvalidToken
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from shared.env import API_SECRET_KEY, FTP_HOOK_SECRET, FTP_PUBLIC_HOST, FTP_PUBLIC_PORT
from shared.factory import db
from shared.modules.torrent_name_parser import parse_title, sanitize

from .common import authenticate_user
from .preferences_utils import serialize_preferences

router = APIRouter()

FTP_USERNAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{2,63}$")


def _ftp_password_cipher():
    key = base64.urlsafe_b64encode(
        hashlib.sha256(str(API_SECRET_KEY).encode("utf-8")).digest()
    )
    return Fernet(key)


def _encrypt_ftp_password(password):
    return _ftp_password_cipher().encrypt(password.encode("utf-8")).decode("utf-8")


def _decrypt_ftp_password(encrypted_password):
    if not encrypted_password:
        return ""
    try:
        return _ftp_password_cipher().decrypt(
            encrypted_password.encode("utf-8")
        ).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):
        return ""


def _ftp_folder_name(source_name, identifier, used_names):
    parsed_name = parse_title(str(source_name or "")) if source_name else ""
    clean_name = parsed_name or sanitize(str(source_name or "")) or "Download"
    # Keep this identical to the homepage torrent label: the first five hash chars.
    suffix = str(identifier or "")[:5]
    base_name = f"{clean_name}-{suffix}" if suffix else clean_name
    folder_name = base_name
    counter = 2
    while folder_name in used_names:
        folder_name = f"{clean_name}-{counter}-{suffix}" if suffix else f"{clean_name}-{counter}"
        counter += 1
    used_names.add(folder_name)
    return folder_name


def _sync_ftp_directory(source_dir, mirror_dir):
    mirror_dir.mkdir(parents=True, exist_ok=True)
    source_entries = {item.name: item for item in source_dir.iterdir() if not item.is_symlink()}

    for mirror_entry in mirror_dir.iterdir():
        if mirror_entry.name not in source_entries:
            if mirror_entry.is_dir() and not mirror_entry.is_symlink():
                shutil.rmtree(mirror_entry)
            else:
                mirror_entry.unlink()

    for name, source_entry in source_entries.items():
        mirror_entry = mirror_dir / name
        if source_entry.is_dir():
            if mirror_entry.exists() and not mirror_entry.is_dir():
                mirror_entry.unlink()
            _sync_ftp_directory(source_entry, mirror_entry)
        elif source_entry.is_file():
            if mirror_entry.exists() and not mirror_entry.is_file():
                if mirror_entry.is_dir():
                    shutil.rmtree(mirror_entry)
                else:
                    mirror_entry.unlink()
            if not mirror_entry.exists():
                try:
                    os.link(source_entry, mirror_entry)
                except OSError:
                    shutil.copy2(source_entry, mirror_entry)


async def _prepare_ftp_friendly_root(user_object_id, user_id, home_dir):
    root_path = Path(os.getenv("DOWNLOAD_PATH", "/downloads")) / str(user_id)
    root_path.mkdir(parents=True, exist_ok=True)
    home_dir.mkdir(parents=True, exist_ok=True)

    torrents = {}
    async for torrent in db.torrents.find(
        {"user_id": {"$in": [user_object_id, str(user_object_id)]}},
        {"info_hash": 1, "url_hash": 1, "name": 1},
    ):
        for identifier in (torrent.get("info_hash"), torrent.get("url_hash")):
            if identifier:
                torrents[str(identifier).lower()] = torrent.get("name") or ""

    used_names = set()
    expected_names = set()
    for source_path in sorted(root_path.iterdir(), key=lambda item: item.name.lower()):
        if not source_path.is_dir() or source_path.resolve() == home_dir.resolve():
            continue

        identifier = source_path.name
        source_name = torrents.get(identifier.lower(), "")
        child_directories = sorted(
            (item for item in source_path.iterdir() if item.is_dir()),
            key=lambda item: item.name.lower(),
        )
        child_files = sorted(
            (item for item in source_path.iterdir() if item.is_file()),
            key=lambda item: item.name.lower(),
        )

        targets = child_directories or [source_path]
        for target in targets:
            display_source = source_name or target.name
            if target == source_path and child_files and not source_name:
                display_source = child_files[0].stem
            folder_name = _ftp_folder_name(display_source, identifier, used_names)
            expected_names.add(folder_name)
            _sync_ftp_directory(target, home_dir / folder_name)

    for item in home_dir.iterdir():
        if item.name not in expected_names:
            if item.is_dir() and not item.is_symlink():
                shutil.rmtree(item)
            else:
                item.unlink()


async def refresh_ftp_friendly_roots():
    async for user in db.users.find(
        {
            "preferences.ftp.enabled": True,
            "preferences.ftp.friendly_names": True,
            "preferences.ftp.username": {"$ne": ""},
        },
        {"_id": 1},
    ):
        user_id = str(user["_id"])
        home_dir = Path(os.getenv("DOWNLOAD_PATH", "/downloads")) / user_id / ".ftp-root"
        await _prepare_ftp_friendly_root(user["_id"], user_id, home_dir)


class FtpSettingsUpdate(BaseModel):
    enabled: bool = False
    username: str = ""
    password: str = ""
    friendly_names: bool = False


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
    raw_ftp = dict((preferences or {}).get("ftp") or {})
    serialized = serialize_preferences(preferences)
    ftp = dict(serialized.get("ftp") or {})
    if ftp.get("username"):
        ftp["url"] = _ftp_url(request, ftp["username"])
        ftp["password"] = _decrypt_ftp_password(raw_ftp.get("password_encrypted"))
    ftp["friendly_names"] = bool(raw_ftp.get("friendly_names"))
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
        "preferences.ftp.friendly_names": bool(settings.friendly_names),
        "preferences.ftp.updated_at": datetime.datetime.utcnow(),
        "preferences.updated_at": datetime.datetime.utcnow(),
    }

    if password:
        salt = bcrypt.gensalt()
        updates["preferences.ftp.password_hash"] = bcrypt.hashpw(
            password.encode("utf-8"),
            salt,
        )
        updates["preferences.ftp.password_encrypted"] = _encrypt_ftp_password(
            password
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
    ftp_preferences = dict((user.get("preferences") or {}).get("ftp") or {})
    if ftp_preferences.get("friendly_names"):
        home_dir = (
            Path(os.getenv("DOWNLOAD_PATH", "/downloads")) / user_id / ".ftp-root"
        )
        await _prepare_ftp_friendly_root(ObjectId(user_id), user_id, home_dir)
        permissions = {"/": ["list", "download"]}
    else:
        home_dir = Path(os.getenv("DOWNLOAD_PATH", "/downloads")) / user_id
        home_dir.mkdir(parents=True, exist_ok=True)
        permissions = {"/": ["*"]}

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
        "permissions": permissions,
        "virtual_folders": [],
        "upload_bandwidth": 0,
        "download_bandwidth": 0,
        "filters": {"allowed_ip": [], "denied_ip": []},
        "public_keys": [],
        "ftp_security": 0,
        "external_auth_cache_time": 0,
    }
