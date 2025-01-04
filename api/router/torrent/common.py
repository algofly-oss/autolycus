from pydantic import BaseModel
from shared.modules.libtorrentx import MagnetUtils
from shared.factory import db, redis
import shutil
import os
import glob


class MagnetDto(BaseModel):
    magnet: str

magnet_utils = MagnetUtils()

def copy_if_already_exists(info_hash, user_id):
    if redis.get(f"{user_id}/{info_hash}/copied_from_existing"):
        return

    existing_save_dirs = glob.glob(f"/downloads/*/{info_hash}")
    if len(existing_save_dirs) > 1:
        for src_save_dir in existing_save_dirs:
            if str(user_id) in src_save_dir:
                continue

            dst_save_dir = os.path.join("/downloads", str(user_id), os.path.basename(src_save_dir))
            os.makedirs(dst_save_dir, exist_ok=True)
            shutil.copytree(src_save_dir, dst_save_dir, dirs_exist_ok=True)
            redis.set(f"{user_id}/{info_hash}/copied_from_existing", 1)

def update_to_db(props, user_id):
    if not user_id:
        return

    props = props.asdict()
    copy_if_already_exists(props.get("info_hash"), user_id)
    db.torrents.update_one({"info_hash": props["info_hash"], "user_id": user_id}, {"$set": props})

async def pause_unfinished_torrents():
    async for torrent in db.torrents.find(
        {
            "$or": [{"is_finished": False}, {"is_finished": {"$exists": False}}],
            "$or": [{"is_paused": False}, {"is_paused": {"$exists": False}}],
        },
        {"_id": True},
    ):
        await db.torrents.update_one(
            {"_id": torrent.get("_id")},
            {"$set": {"is_paused": True, "download_speed": 0}},
        )