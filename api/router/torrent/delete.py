import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from shared.factory import db, redis
from ..auth.common import authenticate_user
from bson import ObjectId
from ..files.delete import delete_dir
import asyncio
from shared.sockets import emit
from .download_status import get_download_status
from ..files.status import get_disk_usage
from shared.modules.file_search_index import (
    delete_document_ids,
    document_ids_for_tree,
    torrent_root_document_id,
)
from shared.modules.media_metadata import delete_media_metadata_for_torrent

router = APIRouter()


class DeleteTorrentRequest(BaseModel):
    info_hash: str


def _download_root():
    return Path(os.getenv("DOWNLOAD_PATH", "/downloads")).resolve()


def _is_within_path(path: Path, parent: Path):
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _remove_empty_parent_dirs(start: Path, stop_at: Path):
    current = start.resolve()
    stop_at = stop_at.resolve()
    while current != stop_at and _is_within_path(current, stop_at):
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def _torrent_storage_paths(user_id: str, torrent: dict, torrent_id: str):
    user_root = (_download_root() / str(user_id)).resolve()
    candidates = []
    save_dir = torrent.get("save_dir")
    if save_dir:
        candidates.append(Path(save_dir))
    if torrent_id:
        candidates.append(user_root / str(torrent_id))

    seen = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved == user_root or not _is_within_path(resolved, user_root):
            continue
        yield resolved, user_root


def _delete_torrent_storage(user_id: str, torrent: dict, torrent_id: str):
    document_ids = []
    for storage_path, user_root in _torrent_storage_paths(user_id, torrent, torrent_id):
        if not storage_path.exists():
            continue

        document_ids.extend(document_ids_for_tree(storage_path, user_id))
        delete_dir(storage_path)
        _remove_empty_parent_dirs(storage_path.parent, user_root)
        break

    return document_ids


@router.post("/delete")
async def delete_torrent(request: DeleteTorrentRequest, request_obj: Request):
    user_id = authenticate_user(request_obj).decode("utf-8")

    if request.info_hash.startswith("url_hash_"):
        url_hash = request.info_hash.lstrip("url_hash_")
        torrent = await db.torrents.find_one(
            {"url_hash": url_hash, "user_id": ObjectId(user_id)},
        )
        if not torrent:
            raise HTTPException(status_code=404, detail="Torrent not found")

        redis.set(f"{user_id}/{torrent['url_hash']}/stop", 1)

        await db.torrents.update_one(
            {"_id": torrent["_id"]}, {"$set": {"is_paused": True}}
        )

        # Check the status in the database every 1 second
        while True:
            updated_torrent = await db.torrents.find_one(
                {"_id": torrent["_id"]}, {"is_paused": True}
            )
            if updated_torrent["is_paused"]:
                break
            await asyncio.sleep(1)

        public_urls_cursor = db.public_urls.find(
            {
                "url_hash": torrent.get("url_hash"),
            }
        )
        public_urls = await public_urls_cursor.to_list(length=None)
        if public_urls:
            await db.public_urls.delete_many(
                {
                    "url_hash": torrent.get("url_hash"),
                }
            )

        document_ids = [torrent_root_document_id(user_id, url_hash)]
        document_ids.extend(_delete_torrent_storage(user_id, torrent, url_hash))
        await delete_document_ids(document_ids)

        await db.torrents.delete_one({"_id": torrent["_id"]})
        await delete_media_metadata_for_torrent(db, user_id, url_hash)

        emit(
            f"/stc/torrent-added-or-removed",
            {"action": "removed", "url_hash": url_hash},
            user_id,
        )
        emit(f"/stc/disk-usage", get_disk_usage(user_id), user_id)
        emit(f"/stc/download_status", await get_download_status(user_id), user_id)
        return {"message": "URL and associated files deleted successfully"}
    else:
        torrent = await db.torrents.find_one(
            {"info_hash": request.info_hash, "user_id": ObjectId(user_id)},
            {
                "_id": True,
                "info_hash": True,
                "is_finished": True,
                "is_paused": True,
                "save_dir": True,
            },
        )

        if torrent:
            if not torrent.get("is_finished"):
                await db.torrents.update_one(
                    {"_id": torrent["_id"]}, {"$set": {"is_paused": True}}
                )
                redis.set(f"{user_id}/{torrent['info_hash']}/stop", 1)

                # Check the status in the database every 1 second
                while True:
                    updated_torrent = await db.torrents.find_one(
                        {"_id": torrent["_id"]}, {"is_paused": True}
                    )
                    if updated_torrent["is_paused"]:
                        break
                    await asyncio.sleep(1)

            public_urls_cursor = db.public_urls.find(
                {
                    "info_hash": torrent.get("info_hash"),
                }
            )
            public_urls = await public_urls_cursor.to_list(length=None)
            if public_urls:
                await db.public_urls.delete_many(
                    {
                        "info_hash": torrent.get("info_hash"),
                    }
                )

            document_ids = [torrent_root_document_id(user_id, request.info_hash)]
            document_ids.extend(
                _delete_torrent_storage(user_id, torrent, request.info_hash)
            )
            await delete_document_ids(document_ids)

            await db.torrents.delete_one({"_id": torrent["_id"]})
            await delete_media_metadata_for_torrent(db, user_id, request.info_hash)

            emit(
                f"/stc/torrent-added-or-removed",
                {"action": "removed", "info_hash": request.info_hash},
                user_id,
            )
            emit(f"/stc/disk-usage", get_disk_usage(user_id), user_id)
            emit(f"/stc/download_status", await get_download_status(user_id), user_id)
            return {"message": "Torrent and associated files deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Torrent not found")
