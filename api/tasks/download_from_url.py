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


@celery_worker.app.task(queue="transcoding")
def download_from_url(url, url_hash, save_dir, user_id):
    redis = Redis(
        host=REDIS_HOST,
        password=REDIS_PASSWORD,
        port=REDIS_PORT,
        db=0,
    )
    mongo_client = MongoClient(os.environ.get("MONGO_DATABASE_URI"))
    db = mongo_client[os.environ.get("MONGO_DATABASE_NAME")]

    download_limit = ""  # "--max-overall-download-limit=1MiB"
    cp = sp.Popen(
        f"aria2c --file-allocation=none -c -x 10 -s 10 --summary-interval=1 --auto-file-renaming=false --allow-overwrite=false --console-log-level=warn --check-certificate=false {download_limit} -d '{save_dir}' '{url}'",
        stdout=sp.PIPE,
        stderr=sp.STDOUT,
        text=True,
        shell=True,
        preexec_fn=os.setsid,
    )

    key = f"{user_id}/{url_hash}/stop"
    redis.delete(key)

    while True:
        line = cp.stdout.readline()
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
            r"(?P<downloaded>\d+(?:\.\d+)?[KMG]iB)/"
            r"(?P<total>\d+(?:\.\d+)?[KMG]iB)\("
            r"(?P<progress>\d+)%\).*?"
            r"DL:(?P<speed>\d+(?:\.\d+)?[KMG]iB).*?"
            r"ETA:(?P<eta>[\dhms]+)",
            line,
        )

        if pattern:
            info = pattern.groupdict()
            info["progress"] = float(info.get("progress", 0))  # 1-100
            info["eta"] = convert_to_seconds(info.get("eta", ""))
            info["speed"] = convert_to_bytes(info.get("speed", "0KiB"))
            info["downloaded"] = convert_to_bytes(info.get("downloaded", "0KiB"))

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

    if redis.get(key):
        redis.delete(key)
        if cp.poll() is None:
            try:
                os.killpg(os.getpgid(cp.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        return {"message": "terminated"}
    else:
        redis.delete(key)
        cp.stdout.close()
        cp.wait()

        db.torrents.update_one(
            {"url_hash": url_hash, "user_id": ObjectId(user_id)},
            {
                "$set": {
                    "is_paused": True,
                    "is_finished": True,
                    "download_speed": 0,
                }
            },
        )
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
