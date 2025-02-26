import socketio
from shared.factory import redis
import re
import asyncio
import traceback

sio = socketio.AsyncServer(
    async_mode="asgi", cors_allowed_origins=[]
)  # [] works for all origins, [*] wasn't working
sio_app = socketio.ASGIApp(socketio_server=sio, socketio_path="/socket.io")


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

    print(f"{sid}: connected")
    await sio.emit("join", {"sid": sid})


@sio.event
async def disconnect(sid):
    print(f"{sid}: disconnected")
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
