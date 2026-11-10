import os
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, conlist
from typing import Optional
from pathlib import Path
import celery_worker
from fastapi.responses import StreamingResponse
from ..auth.common import authenticate_user
from shared.factory import redis
from shared.sockets import emit
from tasks.transcode_video import transcode_video
import json
import time
import asyncio
from .status import get_disk_usage

router = APIRouter()


@router.post("/transcode/start")
async def start_transcode(path: str, resolution: str, request: Request):
    if resolution not in [
        "144p",
        "240p",
        "360p",
        "480p",
        "720p",
        "1080p",
        "1440p",
        "2160p",
    ]:
        raise HTTPException(400, "Invalid resolution")
    user_id = authenticate_user(request)
    from shared.modules.transcode_backend import gpu_enabled, gpu_ready
    if gpu_enabled():
        if not await asyncio.to_thread(gpu_ready):
            raise HTTPException(503, "GPU transcoding is enabled but NVENC is unavailable. Mount the GPU with the optional Compose override or set TRANSCODE_USE_GPU=0.")

    from .playback import media_path
    path = str(media_path(path))
    if not path.startswith(f"/downloads/{user_id.decode()}/"):
        raise HTTPException(status_code=403, detail="Unauthorized Path")

    if redis.get(f"transcoding_progress/{path}"):
        raise HTTPException(409, "Source is still transcoding")

    output_path = f"{os.path.splitext(path)[0]}_{resolution}.mp4"
    if os.path.exists(output_path):
        raise HTTPException(status_code=400, detail="output file already exists")
    else:
        key = f"transcoding_progress/{output_path}"
        redis.delete(f"{key}/error")
        redis.delete(f"{key}/kill")

        with open(output_path, "w") as f:
            f.write("")
            redis.set(key, json.dumps({"progress": 0.01, "eta": 0, "file_size": 0}))

        result = transcode_video.delay(path, output_path, resolution, user_id.decode())
        redis.setex(f"{key}/task", 604800, result.task_id)
        return {
            "message": "Task Added",
            "task_id": result.task_id,
            "output_path": output_path,
        }


@router.post("/transcode/stop")
async def stop_transcode(path: str, request: Request):
    user_id = authenticate_user(request)
    from .playback import media_path
    path = str(media_path(path))
    if not path.startswith(f"/downloads/{user_id.decode()}/"):
        raise HTTPException(status_code=403, detail="Unauthorized Path")

    key = f"transcoding_progress/{path}"
    if redis.get(key):
        redis.setex(f"{key}/kill", 604800, "true")
        task_id = redis.get(f"{key}/task")
        if task_id:
            celery_worker.app.control.revoke(task_id.decode(), terminate=False)
        if os.path.exists(path) and os.path.getsize(path) == 0:
            os.remove(path)
        redis.delete(key)
        return {"message": "Task termination initiated"}
    else:
        return {"message": "No task found for given path"}


@router.post("/transcode/progress")
async def transcode_progress(path: str, request: Request, stream: bool = False):
    user_id = authenticate_user(request)
    if user_id:
        user_id = str(user_id.decode())
    root = Path(os.getenv("DOWNLOAD_PATH", "/downloads")).resolve()
    candidate = (root / path).resolve()
    if root / user_id not in candidate.parents:
        raise HTTPException(status_code=403, detail="Unauthorized Path")
    path = str(candidate)

    key = f"transcoding_progress/{path}"
    if redis.get(key):
        if stream:

            async def event_generator():
                while True:
                    progress_data = redis.get(key)
                    if progress_data:
                        emit(f"/stc/disk-usage", get_disk_usage(user_id), user_id)
                        emit(f"/stc/{key}", json.loads(progress_data), user_id)
                        yield ""
                    else:
                        yield "1"
                        break
                    await asyncio.sleep(1)

            return StreamingResponse(event_generator(), media_type="text/event-stream")
        else:
            return json.loads(redis.get(key))
    else:
        error = redis.get(f"{key}/error")
        return {"status": "failed", "error": error.decode()} if error else {"message": "No task found"}


class BulkTranscode(BaseModel):
    paths: conlist(str, min_items=1, max_items=100)
    action: str
    resolution: Optional[str] = None


@router.post("/transcode/bulk")
async def bulk_transcode(body: BulkTranscode, request: Request):
    user = authenticate_user(request).decode()
    if body.action not in {"start", "cancel"}:
        raise HTTPException(400, "Invalid action")
    if body.action == "start" and body.resolution not in {"144p","240p","360p","480p","720p","1080p","1440p","2160p"}:
        raise HTTPException(400, "Invalid resolution")
    results, visited = [], set()
    for source in body.paths:
        try:
            from .playback import media_path
            file = media_path(source)
            if not str(file).startswith(f"/downloads/{user}/"):
                raise HTTPException(403, "Unauthorized path")
            targets = [file]
            if body.action == "cancel":
                targets += [file.with_name(f"{file.stem}_{height}p.mp4") for height in (144,240,360,480,720,1080,1440,2160)]
                targets = [target for target in targets if redis.get(f"transcoding_progress/{target}")]
            for target in targets:
                if str(target) in visited:
                    continue
                visited.add(str(target))
                result = await start_transcode(str(target), body.resolution, request) if body.action == "start" else await stop_transcode(str(target), request)
                results.append({"path": str(target), "ok": True, **result})
        except HTTPException as error:
            results.append({"path": source, "ok": False, "error": error.detail})
    return {"results": results}
