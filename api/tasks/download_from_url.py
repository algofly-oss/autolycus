import re
import os
import time
import celery_worker
import subprocess as sp
import json
from redis import Redis
from bson import ObjectId
from pymongo import MongoClient
import signal
import selectors
from shared.modules.url_download import aria2_command
from shared.modules.file_search_index import index_torrent_files_sync
from shared.modules.media_metadata import cache_torrent_media_metadata_sync

REDIS_HOST = os.environ.get("REDIS_HOST", None)
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", None)
ETA_PATTERN = re.compile(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?")


def convert_to_seconds(time_str):
    match = ETA_PATTERN.match(time_str)
    hours = int(match.group(1)) if match.group(1) else 0
    minutes = int(match.group(2)) if match.group(2) else 0
    seconds = int(match.group(3)) if match.group(3) else 0
    return hours * 3600 + minutes * 60 + seconds


def convert_to_bytes(speed_str):
    speed_str = speed_str.strip()

    match = re.fullmatch(r"([\d.]+)\s*(B|KiB|MiB|GiB)", speed_str)
    if not match:
        raise ValueError(f"Invalid speed format: {speed_str}")

    value = float(match.group(1))
    unit = match.group(2)

    multipliers = {
        "B": 1,
        "KiB": 1024,
        "MiB": 1024**2,
        "GiB": 1024**3,
    }

    return int(value * multipliers[unit])


@celery_worker.app.task(queue="file_operations")
def download_from_url(url, url_hash, save_dir, user_id):
    redis = Redis(
        host=REDIS_HOST,
        password=REDIS_PASSWORD,
        port=REDIS_PORT,
        db=0,
    )
    mongo_client = MongoClient(os.environ.get("MONGO_DATABASE_URI"))
    db = mongo_client[os.environ.get("MONGO_DATABASE_NAME")]

    os.makedirs(save_dir, exist_ok=True)
    cp = sp.Popen(aria2_command(url, save_dir), stdout=sp.PIPE, stderr=sp.STDOUT, text=True, start_new_session=True)

    key = f"{user_id}/{url_hash}/stop"
    last_downloaded_bytes = 0
    redis.delete(key)

    selector = selectors.DefaultSelector()
    selector.register(cp.stdout, selectors.EVENT_READ)
    pending = ""
    while True:
        if redis.get(key):
            line = ""
        else:
            events = selector.select(timeout=1)
            if not events and cp.poll() is None:
                continue
            chunk = os.read(cp.stdout.fileno(), 65536) if events else b""
            pending = (pending + chunk.decode("utf-8", errors="replace"))[-65536:]
            parts = re.split(r"[\r\n]+", pending)
            if chunk:
                pending = parts.pop()
                if not parts:
                    continue
                line = "\n".join(parts)
                if not line:
                    continue
            else:
                line, pending = pending, ""

        if not line or redis.get(key):
            db.torrents.update_one(
                {"url_hash": url_hash, "user_id": ObjectId(user_id)},
                {
                    "$set": {
                        "is_paused": True,
                        "download_speed": 0,
                    }
                },
            )
            break

        # print(line, end="")
        pattern = re.search(
            r"(?P<downloaded>\d+(?:\.\d+)?(?:[KMG]i)?B)/"
            r"(?P<total>\d+(?:\.\d+)?(?:[KMG]i)?B)\("
            r"(?P<progress>\d+)%\).*?"
            r"DL:(?P<speed>\d+(?:\.\d+)?(?:[KMG]i)?B).*?"
            r"ETA:(?P<eta>[\dhms]+)",
            line,
        )

        if pattern:
            info = pattern.groupdict()
            info["progress"] = float(info.get("progress", 0))  # 1-100
            info["eta"] = convert_to_seconds(info.get("eta", ""))
            info["speed"] = convert_to_bytes(info.get("speed", "0KiB"))
            info["downloaded"] = convert_to_bytes(info.get("downloaded", "0KiB"))
            last_downloaded_bytes = info["downloaded"]

            # print(
            #     f"\nProgress: {info.get('progress')}% | ETA: {info.get('eta') / 60:.2f} min"
            # )

            props = {
                "download_speed": info["speed"],  # bytes / second
                "downloaded_bytes": info["downloaded"],
                "progress": info["progress"],
                "is_paused": False,
                "is_finished": False,
            }

            db.torrents.update_one(
                {"url_hash": url_hash, "user_id": ObjectId(user_id)}, {"$set": props}
            )
            props["url_hash"] = url_hash
            payload = json.dumps(
                {
                    "action": "emit",
                    "user_id": user_id,
                    "progress": info.get("progress"),
                    "eta": info.get("eta"),
                    "url_hash": url_hash,
                    "props": props,
                }
            )
            redis.publish("events", payload)

    selector.close()
    if redis.get(key):
        redis.delete(key)
        if cp.poll() is None:
            try:
                os.killpg(os.getpgid(cp.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        cp.wait()
        cp.stdout.close()
        mongo_client.close()
        redis.close()
        return {"message": "terminated"}
    else:
        redis.delete(key)
        cp.stdout.close()
        cp.wait()
        if cp.returncode != 0:
            db.torrents.update_one({"url_hash": url_hash, "user_id": ObjectId(user_id)}, {"$set": {"is_paused": True, "is_finished": False, "download_speed": 0, "download_error": f"aria2 exited with status {cp.returncode}"}})
            mongo_client.close()
            redis.close()
            raise RuntimeError(f"Download failed (aria2 exit {cp.returncode})")

        # Some servers omit Content-Length. Use aria2's final transfer count,
        # not the save directory size: it may later also contain extracted files.
        completed_bytes = last_downloaded_bytes
        if not completed_bytes:
            torrent = db.torrents.find_one({"url_hash": url_hash, "user_id": ObjectId(user_id)})
            filename = torrent.get("name") if torrent else None
            archive_path = os.path.join(save_dir, filename) if filename else None
            if archive_path and os.path.isfile(archive_path):
                completed_bytes = os.path.getsize(archive_path)

        db.torrents.update_one(
            {"url_hash": url_hash, "user_id": ObjectId(user_id)},
            {
                "$set": {
                    "is_paused": True,
                        "is_finished": True,
                        "download_speed": 0,
                        "downloaded_bytes": completed_bytes,
                        "total_bytes": completed_bytes or None,
                        "progress": 100,
                }
            },
        )
        torrent = db.torrents.find_one({"url_hash": url_hash, "user_id": ObjectId(user_id)})
        if torrent:
            try:
                index_torrent_files_sync(user_id, torrent)
                cache_torrent_media_metadata_sync(db, user_id, torrent)
                from tasks.media_previews import preview_download_tree
                preview_download_tree.delay(save_dir)
            except Exception:
                pass
        payload = json.dumps(
            {
                "action": "emit",
                "user_id": user_id,
                "progress": 100,
                "eta": 0,
                "url_hash": url_hash,
                "props": {
                    "download_speed": 0,
                    "progress": 100,
                    "is_paused": True,
                    "is_finished": True,
                },
            }
        )
        redis.publish("events", payload)

        if os.path.exists(save_dir):
            return {"message": "success"}
        else:
            raise Exception("Downloading failed: Unable to generate output file")
