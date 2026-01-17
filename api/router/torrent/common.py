from pydantic import BaseModel
from shared.modules.libtorrentx import MagnetUtils
from shared.factory import db, redis
from shared.sockets import emit
from ..files.status import get_disk_usage
from .download_status import get_download_status
import shutil
import os
import glob
import asyncio


class MagnetDto(BaseModel):
    magnet: str


class UrlDto(BaseModel):
    url: str


magnet_utils = MagnetUtils()


def get_directory_size(directory):
    return sum(f.stat().st_size for f in os.scandir(directory) if f.is_file())


def copy_if_already_exists(info_hash, user_id):
    if redis.get(f"{user_id}/{info_hash}/copied_from_existing"):
        return

    existing_directories = glob.glob(f"/downloads/*/{info_hash}")
    current_user_directory = os.path.join(f"/downloads/{user_id}/{info_hash}")

    if len(existing_directories):
        try:
            other_user_directories = [
                directory
                for directory in existing_directories
                if str(user_id) not in directory
            ]
            if other_user_directories:
                # Find the directory with the largest size
                largest_directory = max(other_user_directories, key=get_directory_size)
                # shutil.copytree(largest_directory, current_user_directory, dirs_exist_ok=True)
                os.system(f"rsync -a {largest_directory}/ {current_user_directory}/")
                redis.set(f"{user_id}/{info_hash}/copied_from_existing", 1)
                redis.expire(f"{user_id}/{info_hash}/copied_from_existing", 60 * 60)
        except Exception as error:
            print(error)


def update_to_db(props, user_id):
    if not user_id:
        return

    props = props.asdict()
    copy_if_already_exists(props.get("info_hash"), user_id)

    if props.get("is_finished") or props.get("is_paused"):
        redis.delete(f"{user_id}/{props['info_hash']}/copied_from_existing")

    # Update torrent progress via socket.io
    emit(f"/stc/torrent-props-update/{props.get('info_hash')}", props, user_id)
    emit(f"/stc/disk-usage", get_disk_usage(str(user_id)), user_id)
    # emit(f"/stc/download_status", await get_download_status(user_id), user_id)
    db.torrents.update_one(
        {"info_hash": props["info_hash"], "user_id": user_id}, {"$set": props}
    )


async def pause_unfinished_torrents():
    async for torrent in db.torrents.find(
        {
            "$or": [{"is_finished": False}, {"is_finished": {"$exists": False}}],
            "$or": [{"is_paused": False}, {"is_paused": {"$exists": False}}],
        },
        {"_id": True, "is_direct_download": True},
    ):
        if torrent.get("is_direct_download"):
            continue

        await db.torrents.update_one(
            {"_id": torrent.get("_id")},
            {"$set": {"is_paused": True, "download_speed": 0}},
        )
