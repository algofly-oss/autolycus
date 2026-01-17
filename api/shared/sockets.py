import socketio
from shared.factory import redis
import re
import os
import asyncio
import traceback
import threading
import time
import logging
import json
import shutil
from pathlib import Path

sio = socketio.AsyncServer(
    async_mode="asgi", cors_allowed_origins=[]
)  # [] works for all origins, [*] wasn't working
sio_app = socketio.ASGIApp(socketio_server=sio, socketio_path="/socket.io")


def get_disk_usage(user_id):
    try:
        total = shutil.disk_usage("/downloads").total
        occupied_by_user = 0
        if os.path.exists(f"/downloads/{user_id}"):
            occupied_by_user = sum(
                f.stat().st_blocks * 512
                for f in Path(f"/downloads/{user_id}").rglob("*")
                if f.is_file()
            )
        occupied_by_others = shutil.disk_usage("/downloads").used - occupied_by_user

        return {"used": occupied_by_user, "total": total - occupied_by_others}
    except Exception as e:
        traceback.print_exc()
        return {"used": 0, total: 0}


def subscriber():
    while True:
        try:
            pubsub = redis.pubsub()
            pubsub.subscribe("events")

            # logging.error(f"✅ Subscribed to Redis channel: events")

            for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                data = json.loads(message["data"].decode())
                # logging.error(f"📩 Received message: {data}")

                if data.get("action") == "emit":
                    user_id = data.get("user_id")
                    url_hash = data.get("url_hash")
                    props = data.get("props")
                    emit(f"/stc/torrent-props-update/{url_hash}", props, user_id)
                    emit(f"/stc/disk-usage", get_disk_usage(str(user_id)), user_id)
                    if props.get("is_finished"):
                        emit(
                            f"/stc/torrent-added-or-removed",
                            {"action": "finished", "url_hash": url_hash},
                            user_id,
                        )
        except:
            time.sleep(1)
            traceback.print_exc()


threading.Thread(target=subscriber, daemon=True).start()


@sio.event
async def connect(sid, environ, auth):
    pattern = r"session_token=([^;]+)"
    match = re.search(pattern, environ.get("HTTP_COOKIE", ""))
    session_token = match.group(1) if match else None

    if session_token:
        user_id = redis.get(session_token)
        if user_id:
            user_id = user_id.decode()
            await sio.enter_room(sid, user_id)

    # print(f"{sid}: connected")
    await sio.emit("join", {"sid": sid})


@sio.event
async def disconnect(sid):
    # print(f"{sid}: disconnected")
    await sio.disconnect(sid)


def emit(event_name, data, user_id):
    async def _emit(event_name, data, user_id):
        try:
            if asyncio.iscoroutine(data):
                return
            await sio.emit(event_name, data=data, room=str(user_id))
        except Exception as e:
            # traceback.print_exc()
            print(e)

    try:
        # If there's a running event loop, use create_task
        loop = asyncio.get_running_loop()
        loop.create_task(_emit(event_name, data, user_id))
    except Exception:
        # If there's no running event loop, use asyncio.run
        asyncio.run(_emit(event_name, data, user_id))
