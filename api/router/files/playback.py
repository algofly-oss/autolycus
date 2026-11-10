"""Byte-only playback control. No probing, remuxing or transcoding on the server."""
import hashlib
import mimetypes
import os
import secrets
import re
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, constr
from shared.factory import redis
from ..auth.common import authenticate_user, get_session_token

router = APIRouter(prefix="/playback")
CONTROL = "http://127.0.0.1:9088"


def media_path(path):
    root = Path(os.getenv("DOWNLOAD_PATH", "/downloads")).resolve()
    candidate = (root / path).resolve()
    if root not in candidate.parents:
        raise HTTPException(403, "Access denied")
    if not candidate.is_file():
        raise HTTPException(404, "File not found")
    return candidate


def session_owner(request):
    authenticate_user(request)
    return hashlib.sha256(get_session_token(request).encode()).hexdigest()


def check_origin(request):
    # Browser control requests must be same-origin. No cross-site allocation.
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
        from urllib.parse import urlsplit
        if urlsplit(origin).netloc != request.headers.get("host"):
            raise HTTPException(403, "Invalid origin")


QUALITY_HEIGHTS = (144, 240, 360, 480, 720, 1080, 1440, 2160)


def quality_versions(file):
    root = Path(os.getenv("DOWNLOAD_PATH", "/downloads")).resolve()
    siblings = list(file.parent.iterdir())
    match = re.fullmatch(r"(.+)_(144|240|360|480|720|1080|1440|2160)p", file.stem)
    original = file
    if match:
        candidates = [entry for entry in siblings if entry.stem == match[1] and entry.suffix.lower() in (".mkv", ".mp4", ".avi", ".mov", ".webm", ".m4v", ".ts", ".m2ts") and entry.is_file() and not entry.is_symlink()]
        if candidates:
            original = sorted(candidates, key=lambda entry: entry.name)[0]
    versions = [{"quality": "original", "path": str(original.relative_to(root)), "size": original.stat().st_size}]
    for height in QUALITY_HEIGHTS:
        candidate = original.with_name(f"{original.stem}_{height}p.mp4")
        if candidate != original and candidate.is_file() and not candidate.is_symlink() and candidate.stat().st_size > 0 and not redis.get(f"transcoding_progress/{candidate}"):
            versions.append({"quality": f"{height}p", "height": height, "path": str(candidate.relative_to(root)), "size": candidate.stat().st_size})
    return versions


@router.get("/info")
async def info(request: Request, path: str):
    authenticate_user(request)
    file = media_path(path)
    redis.setex("media-playback-active",45,1)
    # Sidecar text subtitles only; enumeration is bounded, no content scanning.
    subtitles = []
    for entry in file.parent.iterdir():
        if len(subtitles) >= 32:
            break
        if entry.is_file() and entry.suffix.lower() in (".vtt", ".srt") and (entry.stem == file.stem or entry.stem.startswith(file.stem + ".")):
            language = entry.stem.rsplit(".",1)[-1].lower()
            subtitles.append({"language": language if re.fullmatch(r"[a-z]{2,3}",language) else "und", "name": entry.name, "path": str(entry.relative_to(Path(os.getenv("DOWNLOAD_PATH", "/downloads")).resolve()))})
    return {"versions": quality_versions(file), "size": file.stat().st_size, "type": mimetypes.guess_type(file.name)[0] or "application/octet-stream", "subtitles": subtitles,
            "direct": os.getenv("WEBRTC_ENABLED", "1") == "1"}


class Offer(BaseModel):
    path: constr(max_length=4096)
    sdp: constr(max_length=32768)


@router.post("/offer")
async def offer(request: Request, body: Offer):
    owner = session_owner(request)
    check_origin(request)
    if os.getenv("WEBRTC_ENABLED", "1") != "1":
        raise HTTPException(503, "Direct playback unavailable")
    file = media_path(body.path)
    key = "playback-rate:" + owner
    count = redis.incr(key)
    if count == 1:
        redis.expire(key, 60)
    if count > 12:
        raise HTTPException(429, "Too many connection attempts")
    peer = secrets.token_hex(32)
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(CONTROL + "/offer", json={"id": peer, "path": str(file), "offer": {"type": "offer", "sdp": body.sdp}})
        if response.status_code != 200:
            raise HTTPException(503, "Direct playback unavailable")
        redis.setex("playback-peer:" + peer, 65, owner)
        redis.setex("media-playback-active",45,1)
        return {**response.json(), "id": peer}
    except httpx.HTTPError:
        raise HTTPException(503, "Direct playback unavailable")


class Lease(BaseModel):
    id: constr(regex=r"^[0-9a-f]{64}$")
    close: bool = False


@router.post("/lease")
async def lease(request: Request, body: Lease):
    owner = session_owner(request)
    check_origin(request)
    key = "playback-peer:" + body.id
    saved = redis.get(key)
    if not saved or saved.decode() != owner:
        raise HTTPException(404, "Connection ended")
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.post(CONTROL + "/lease", json=body.dict())
        if response.status_code != 204:
            raise HTTPException(404, "Connection ended")
    except httpx.HTTPError:
        raise HTTPException(503, "Connection unavailable")
    if not body.close:redis.setex("media-playback-active",45,1)
    if body.close:
        redis.delete(key)
    else:
        redis.expire(key, 65)
    return {"ok": True}


@router.get("/subtitle")
async def subtitle(request: Request, path: str):
    authenticate_user(request)
    file = media_path(path)
    if file.suffix.lower() not in (".vtt", ".srt") or file.stat().st_size > 2 * 1024 * 1024:
        raise HTTPException(400, "Unsupported subtitle")
    return FileResponse(file, media_type="text/plain", headers={"Cache-Control": "no-store"})
