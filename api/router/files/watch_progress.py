"""Small per-account playback bookmarks; never reads video contents."""
import asyncio
from datetime import datetime
import os
from pathlib import Path
import re
from typing import List
from bson import ObjectId
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, confloat, constr, conlist
from shared.factory import db, redis
from shared.modules.media_profiles import profile_id
from pymongo.errors import OperationFailure
from shared.modules.folder_watch import cached_inventory,combine
from ..auth.common import authenticate_user
from .playback import media_path, check_origin, quality_versions

router = APIRouter(prefix="/playback")
_indexed = False


def relative_path(path):
    root = Path(os.getenv("DOWNLOAD_PATH", "/downloads")).resolve()
    candidate = (root / path).resolve()
    if root != candidate and root not in candidate.parents:
        raise HTTPException(403, "Access denied")
    return str(candidate.relative_to(root))


async def collection():
    global _indexed
    if not _indexed:
        await db.watch_progress.update_many({"profile_id":{"$exists":False}},{"$set":{"profile_id":"default"}})
        try:
            await db.watch_progress.drop_index("user_id_1_path_1")
        except OperationFailure as error:
            if error.code not in (26,27):
                raise
        await db.watch_progress.create_index([("user_id", 1), ("profile_id",1), ("path", 1)], unique=True)
        await db.watch_progress.create_index([("user_id", 1), ("profile_id",1), ("updated_at", -1)])
        _indexed = True
    return db.watch_progress


def canonical_path(path):
    relative = relative_path(path)
    if re.search(r"_(144|240|360|480|720|1080|1440|2160)p\.mp4$", relative):
        try:
            return quality_versions(media_path(relative))[0]["path"]
        except HTTPException:
            pass
    return relative


def visible(doc):
    if not doc:
        return None
    return {key: doc[key] for key in ("path", "position", "duration", "completed")}


class Bookmark(BaseModel):
    path: constr(min_length=1, max_length=4096)
    position: confloat(ge=0, le=604800, allow_inf_nan=False)
    duration: confloat(gt=0, le=604800, allow_inf_nan=False)
    completed: bool = False


@router.post("/progress")
async def save_progress(body: Bookmark, request: Request):
    user = authenticate_user(request).decode()
    selected=await profile_id(request,user)
    check_origin(request)
    file = media_path(body.path)
    path = canonical_path(str(file))
    redis.setex("media-playback-active",45,1)
    position = min(body.position, body.duration)
    doc = {"user_id": user, "profile_id":selected, "path": path, "position": position, "duration": body.duration,
           "completed": body.completed or body.duration-position < 2, "updated_at": datetime.utcnow()}
    await (await collection()).update_one({"user_id": user, "profile_id":selected, "path": path}, {"$set": doc}, upsert=True)
    return visible(doc)


@router.get("/progress")
async def get_progress(path: str, request: Request):
    user = authenticate_user(request).decode()
    doc = await (await collection()).find_one({"user_id": user, "profile_id":await profile_id(request,user), "path": canonical_path(path)})
    return {"progress": visible(doc)}


class ProgressPath(BaseModel):
    path: constr(min_length=1, max_length=4096)
    directory: bool = False


class ProgressBatch(BaseModel):
    entries: conlist(ProgressPath, max_items=200)


@router.post("/progress/batch")
async def progress_batch(body: ProgressBatch, request: Request):
    user = authenticate_user(request).decode()
    selected=await profile_id(request,user)
    coll = await collection()
    slots = asyncio.Semaphore(8)
    async def find(entry):
        path = relative_path(entry.path)
        query = {"user_id": user, "profile_id":selected, "path": {"$regex": "^" + re.escape(path.rstrip("/")) + "/"} if entry.directory else canonical_path(path)}
        async with slots:
            if entry.directory:
                root=Path(os.getenv("DOWNLOAD_PATH","/downloads")).resolve();directory=(root/path).resolve()
                if not Path(path).parts or Path(path).parts[0]!=user or directory==root or (root not in directory.parents) or directory.is_symlink():return path,None
                groups=await asyncio.to_thread(cached_inventory,directory,root,redis)
                if groups is None:return path,None
                docs=await coll.find(query).to_list(length=4000)
                return path,combine(path,groups,docs)
            doc = await coll.find_one(query, sort=[("updated_at", -1)])
        return path, visible(doc)
    return {"progress": dict(await asyncio.gather(*(find(entry) for entry in body.entries)))}
