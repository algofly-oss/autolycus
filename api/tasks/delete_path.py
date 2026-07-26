import os
import shutil
from pathlib import Path

from pymongo import MongoClient

import celery_worker
from shared.env import MONGO_DATABASE_NAME, MONGO_DATABASE_URI
from shared.modules.file_search_index import delete_document_ids_sync, document_ids_for_tree
from shared.sockets import emit


DOWNLOAD_ROOT = Path(os.getenv("DOWNLOAD_PATH", "/downloads")).resolve()


def _within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _disk_usage(user_id):
    total = shutil.disk_usage(DOWNLOAD_ROOT).total
    user_root = DOWNLOAD_ROOT / str(user_id)
    occupied_by_user = sum(
        item.stat().st_blocks * 512
        for item in user_root.rglob("*")
        if item.is_file()
    ) if user_root.exists() else 0
    occupied_by_others = shutil.disk_usage(DOWNLOAD_ROOT).used - occupied_by_user
    return {"used": occupied_by_user, "total": total - occupied_by_others}


@celery_worker.app.task(queue="file_operations")
def delete_path(relative_path, user_id):
    """Delete a user-owned path and its metadata outside the API request cycle."""
    target = (DOWNLOAD_ROOT / relative_path.lstrip("/")).resolve()
    user_root = (DOWNLOAD_ROOT / str(user_id)).resolve()
    if not _within(target, user_root) or not target.exists():
        raise ValueError("Invalid or missing delete path")

    document_ids = document_ids_for_tree(target, user_id)
    if target.is_file():
        relative_paths = [target.relative_to(DOWNLOAD_ROOT).as_posix()]
    else:
        relative_paths = [
            child.relative_to(DOWNLOAD_ROOT).as_posix()
            for child in target.rglob("*")
            if child.is_file()
        ]

    parts = Path(relative_path).parts
    torrent_id = parts[1] if len(parts) > 1 else None
    mongo_client = MongoClient(MONGO_DATABASE_URI)
    database = mongo_client[MONGO_DATABASE_NAME]
    try:
        database.public_urls.delete_many(
            {
                "$or": [{"info_hash": torrent_id}, {"url_hash": torrent_id}],
                "path": str(target),
            }
        )
        if target.is_file() or target.is_symlink():
            target.unlink()
        else:
            shutil.rmtree(target)
        delete_document_ids_sync(document_ids)
        if relative_paths:
            database.movie_metadata.delete_many(
                {"user_id": str(user_id), "relative_path": {"$in": relative_paths}}
            )
    finally:
        mongo_client.close()

    emit(f"/stc/disk-usage", _disk_usage(user_id), str(user_id))
    return {"message": "success", "path": relative_path}
