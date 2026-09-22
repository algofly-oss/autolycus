import os
import re
from pathlib import Path
from urllib.parse import quote

import zipstream
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request
from starlette.responses import StreamingResponse

from shared.factory import db
from ..auth.common import authenticate_user

router = APIRouter()

_UNSAFE_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def _sanitize_filename(name: str, fallback: str) -> str:
    cleaned = _UNSAFE_FILENAME_CHARS.sub("", name).strip(" .")
    return cleaned[:150] if cleaned else fallback


def _download_root() -> Path:
    return Path(os.getenv("DOWNLOAD_PATH", "/downloads")).resolve()


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _resolve_torrent_dir(user_id: str, torrent: dict, torrent_id: str) -> Path:
    user_root = (_download_root() / user_id).resolve()
    candidates = []
    save_dir = torrent.get("save_dir")
    if save_dir:
        candidates.append(Path(save_dir))
    candidates.append(user_root / torrent_id)

    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved == user_root or not _is_within(resolved, user_root):
            continue
        if resolved.exists():
            return resolved

    raise HTTPException(status_code=404, detail="Torrent files not found")


@router.get("/download-zip")
async def download_torrent_zip(info_hash: str, request: Request, filename: str = None):
    user_id = authenticate_user(request).decode()

    if info_hash.startswith("url_hash_"):
        url_hash = info_hash[len("url_hash_"):]
        torrent = await db.torrents.find_one(
            {"url_hash": url_hash, "user_id": ObjectId(user_id)}
        )
        torrent_id = url_hash
    else:
        torrent = await db.torrents.find_one(
            {"info_hash": info_hash, "user_id": ObjectId(user_id)}
        )
        torrent_id = info_hash

    if not torrent:
        raise HTTPException(status_code=404, detail="Torrent not found")

    directory = _resolve_torrent_dir(user_id, torrent, torrent_id)
    base_name = _sanitize_filename(filename, directory.name) if filename else directory.name
    zip_name = f"{base_name}.zip"

    def stream():
        zs = zipstream.ZipStream(compress_type=zipstream.ZIP_DEFLATED)
        zs.add_path(directory, arcname=directory.name)
        for chunk in zs:
            yield chunk

    ascii_fallback = zip_name.encode("ascii", "ignore").decode("ascii") or "download.zip"
    return StreamingResponse(
        stream(),
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{ascii_fallback}"; '
                f"filename*=UTF-8''{quote(zip_name)}"
            )
        },
    )
