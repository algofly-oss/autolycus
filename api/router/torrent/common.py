from pydantic import BaseModel
from shared.modules.libtorrentx import LibTorrentSession
from shared.modules.libtorrentx import MagnetUtils
from shared.factory import db, redis


class MagnetDto(BaseModel):
    magnet: str


lt_session = LibTorrentSession(redis=redis)
magnet_utils = MagnetUtils()

def update_to_db(props, user_id=None):
    props = props.asdict()
    if user_id:
        props["user_id"] = user_id

    db.torrents.update_one({"info_hash": props["info_hash"]}, {"$set": props})
    key = f"{props['info_hash']}/progress"
    redis.set(key, props["progress"])
    redis.expire(key, 60)

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