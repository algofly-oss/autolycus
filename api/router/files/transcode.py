import os
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from ..auth.common import authenticate_user
from shared.factory import redis
from shared.sockets import emit
from tasks.transcode_video import transcode_video
import json
import time
import asyncio

router = APIRouter()


@router.post("/transcode/start")
async def transcode(path: str, resolution: str, request: Request):
    assert resolution in [
        "144p",
        "240p",
        "360p",
        "480p",
        "720p",
        "1080p",
        "1440p",
        "2160p",
    ], "Invalid Resolution"
    user_id = authenticate_user(request.cookies.get("session_token"))

    if not os.path.exists(path):
        raise HTTPException(status_code=400, detail="Invalid Path")

    if not path.lstrip("/downloads/").startswith(user_id.decode()):
        raise HTTPException(status_code=403, detail="Unauthorized Path")

    output_path = f"{os.path.splitext(path)[0]}_{resolution}.mp4"
    if os.path.exists(output_path):
        raise HTTPException(status_code=400, detail="output file already exists")
    else:
        key = f"transcoding_progress/{output_path}"
        redis.delete(f"{key}/kill")

        with open(output_path, "w") as f:
            f.write("")
            redis.set(key, json.dumps({"progress": 0.01, "eta": 0}))

        result = transcode_video.delay(path, output_path, resolution, user_id.decode())
        return {
            "message": "Task Added",
            "task_id": result.task_id,
            "output_path": output_path,
        }


@router.post("/transcode/stop")
async def transcode(path: str, request: Request):
    user_id = authenticate_user(request.cookies.get("session_token"))
    if not path.lstrip("/downloads/").startswith(user_id.decode()):
        raise HTTPException(status_code=403, detail="Unauthorized Path")

    key = f"transcoding_progress/{path}"
    if redis.get(key):
        redis.set(f"{key}/kill", "true")
        return {"message": "Task termination initiated"}
    else:
        return {"message": "No task found for given path"}


@router.post("/transcode/progress")
async def transcode(path: str, request: Request, stream: bool = False):
    user_id = authenticate_user(request.cookies.get("session_token"))
    if not path.lstrip("/downloads/").startswith(user_id.decode()):
        raise HTTPException(status_code=403, detail="Unauthorized Path")

    key = f"transcoding_progress/{path}"
    if redis.get(key):
        if stream:

            async def event_generator():
                while True:
                    progress_data = redis.get(key)
                    if progress_data:
                        emit(f"/stc/{key}", json.loads(progress_data), user_id.decode())
                        yield ""
                    else:
                        yield "1"
                        break
                    await asyncio.sleep(1)

            return StreamingResponse(event_generator(), media_type="text/event-stream")
        else:
            return json.loads(redis.get(key))
    else:
        return {"message": "No task found"}
