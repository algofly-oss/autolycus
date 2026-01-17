import hashlib
from fastapi import APIRouter, Request, Response, HTTPException, UploadFile, File
from pydantic import BaseModel
from shared.factory import db, redis
from shared.sockets import emit
from ..auth.common import authenticate_user
from .common import (
    MagnetDto,
    UrlDto,
    magnet_utils,
    pause_unfinished_torrents,
    update_to_db,
    copy_if_already_exists,
)
from .download_status import get_download_status
from shared.modules.libtorrentx import LibTorrentSession
from bson import ObjectId
import asyncio
import datetime
import tempfile
import os
import subprocess as sp
import traceback
import json
from tasks.download_from_url import download_from_url

router = APIRouter()

# On app reload, update status of any downloading torrent status to paused,
# as they may be killed already due to app reload
asyncio.create_task(pause_unfinished_torrents())


@router.post("/add")
async def add_torrent(dto: MagnetDto, request: Request):
    user_id = authenticate_user(request.cookies.get("session_token")).decode("utf-8")

    # extract info_hash from magnet
    info_hash = magnet_utils._clean_magnet_uri(dto.magnet).split(":")[3][:40]

    lt_session = LibTorrentSession(redis=redis)

    # add torrent to db
    already_exists = await db.torrents.find_one(
        {"info_hash": info_hash, "user_id": ObjectId(user_id)},
        {"_id": True, "is_paused": True, "is_finished": True},
    )

    if already_exists:
        await db.torrents.update_one(
            {"_id": already_exists.get("_id")},
            {"$set": {"is_paused": False, "is_finished": False}},
        )
    else:
        await db.torrents.insert_one(
            {
                "info_hash": info_hash,
                "user_id": ObjectId(user_id),
                "magnet": dto.magnet,
                "created_at": datetime.datetime.now(),
            }
        )
        emit(
            f"/stc/torrent-added-or-removed",
            {"action": "added", "info_hash": info_hash},
            user_id,
        )

    redis.delete(f"{user_id}/{info_hash}/stop")
    redis.delete(f"{user_id}/{info_hash}/copied_from_existing")

    handle = lt_session.add_torrent(dto.magnet, f"/downloads/{user_id}")
    handle.set_callback(
        lambda props: update_to_db(props, ObjectId(user_id)),
        callback_interval=1,
        user_id=user_id,
    )

    return {"message": "Magnet Exists" if already_exists else "Magnet Added"}


@router.post("/add-file")
async def add_torrent_file(request: Request, torrent: UploadFile = File(...)):
    user_id = authenticate_user(request.cookies.get("session_token")).decode("utf-8")

    # Save the uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".torrent") as temp_file:
        content = await torrent.read()
        temp_file.write(content)
        temp_file_path = temp_file.name

    try:
        lt_session = LibTorrentSession(redis=redis)
        # Convert .torrent file to magnet link
        magnet = lt_session._get_magnet_from_torrent_file(temp_file_path)

        # extract info_hash from magnet
        info_hash = magnet_utils._clean_magnet_uri(magnet).split(":")[3][:40]

        # Check if torrent already exists
        already_exists = await db.torrents.find_one(
            {"info_hash": info_hash, "user_id": ObjectId(user_id)},
            {"_id": True, "is_paused": True, "is_finished": True},
        )

        if already_exists:
            await db.torrents.update_one(
                {"_id": already_exists.get("_id")},
                {"$set": {"is_paused": False, "is_finished": False}},
            )
        else:
            await db.torrents.insert_one(
                {
                    "info_hash": info_hash,
                    "user_id": ObjectId(user_id),
                    "magnet": magnet,
                    "created_at": datetime.datetime.now(),
                }
            )
            emit(
                f"/stc/torrent-added-or-removed",
                {"action": "added", "info_hash": info_hash},
                user_id,
            )
            emit(f"/stc/download_status", await get_download_status(user_id), user_id)

        redis.delete(f"{user_id}/{info_hash}/stop")
        redis.delete(f"{user_id}/{info_hash}/copied_from_existing")

        handle = lt_session.add_torrent(magnet, f"/downloads/{user_id}")
        handle.set_callback(
            lambda props: update_to_db(props, ObjectId(user_id)),
            callback_interval=1,
            user_id=user_id,
        )

        return {"message": "Magnet Exists" if already_exists else "Magnet Added"}

    finally:
        # Clean up the temporary file
        os.unlink(temp_file_path)


def get_filename_from_url(url):
    result = sp.run(
        f"aria2c --check-certificate=false --console-log-level=info --dry-run '{url}'",
        shell=True,
        stdout=sp.PIPE,
        stderr=sp.PIPE,
        text=True,
    )

    response = {"filename": None, "content_type": None, "content_length": None}
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            if "Download complete:" in line:
                try:
                    path = line.split("Download complete:", 1)[1].strip()
                    response["filename"] = path.split("/")[-1]
                except:
                    traceback.print_exc()

            elif "Content-Type:" in line:
                try:
                    response["content_type"] = line.split(": ")[-1]
                except:
                    traceback.print_exc()

            elif "Content-Length:" in line:
                try:
                    response["content_length"] = int(line.split(": ")[-1])
                except:
                    traceback.print_exc()
    else:
        print(f"Error: {result.stderr}")

    return response


@router.post("/add-url")
async def direct_download(dto: UrlDto, request: Request):
    user_id = authenticate_user(request.cookies.get("session_token")).decode("utf-8")

    try:
        file_info = get_filename_from_url(dto.url)
        if (not file_info.get("filename")) or file_info.get(
            "content_type"
        ) != "application/octet-stream":
            raise HTTPException(status_code=404, detail="Invalid URL")

        url_hash = hashlib.md5(dto.url.encode()).hexdigest()
        save_dir = f"/downloads/{user_id}/{url_hash}"

        already_exists = await db.torrents.find_one(
            {"url_hash": url_hash, "user_id": ObjectId(str(user_id))},
        )

        obj = {
            "user_id": ObjectId(str(user_id)),
            "name": file_info.get("filename", "Unknown"),
            "is_direct_download": True,
            "url": dto.url,
            "url_hash": url_hash,
            "ok": True,
            "download_speed": 0,
            "downloaded_bytes": 0,
            "total_bytes": file_info.get("content_length", 0),
            "progress": 0,
            "save_dir": save_dir,
            "is_paused": False,
            "is_finished": False,
            "created_at": datetime.datetime.now(),
        }

        if already_exists:
            return {"message": "URL Exists"}

        await db.torrents.insert_one(obj)

        result = download_from_url.delay(dto.url, url_hash, save_dir, str(user_id))

        emit(
            f"/stc/torrent-added-or-removed",
            {"action": "added", "url_hash": url_hash},
            user_id,
        )

        return {"message": "URL added"}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to add URL")
