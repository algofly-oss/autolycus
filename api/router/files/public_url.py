import os
import hashlib
import re
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from ..auth.common import authenticate_user
from pydantic import BaseModel
from shared.factory import db
from shared.modules.torrent_name_parser import parse_title
from datetime import datetime
from .stream import handle_stream_file
import traceback

router = APIRouter()


class Payload(BaseModel):
    path: str
    key: Optional[str] = None


class PublicUrlBulkDeactivatePayload(BaseModel):
    path_hashes: Optional[List[str]] = None
    all: bool = False


def public_url_document(doc):
    path = doc.get("path") or ""
    return {
        "key": doc.get("title") or doc.get("path_hash"),
        "path_hash": doc.get("path_hash"),
        "path": path,
        "name": os.path.basename(path),
        "info_hash": doc.get("info_hash"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


def public_url_key_for_path(info_hash: str, path: str, torrent_name: str = ""):
    path_hash = hashlib.md5(f"{info_hash}/{path}".encode()).hexdigest()[:10]

    try:
        title = parse_title(torrent_name + " " + os.path.basename(path))
        title, ext = os.path.splitext(title)
        return path_hash, f"{title}-{path_hash}{ext}"
    except Exception:
        traceback.print_exc()
        return path_hash, path_hash


async def ensure_public_url_record(
    user_id: str,
    info_hash: str,
    path: str,
    active: bool = False,
    key: Optional[str] = None,
):
    torrent_name = ""
    torrent = await db.torrents.find_one({"info_hash": info_hash})
    if torrent:
        torrent_name = torrent.get("name", "")

    requested_key = (key or "").strip()
    if requested_key:
        if not re.fullmatch(r"[A-Za-z0-9_-]{12,80}", requested_key):
            raise HTTPException(status_code=400, detail="Invalid public URL key")
        existing_key = await db.public_urls.find_one(
            {"$or": [{"title": requested_key}, {"path_hash": requested_key}]}
        )
        if existing_key and existing_key.get("path") != path:
            raise HTTPException(status_code=409, detail="Public URL key already exists")
        path_hash = requested_key
        title = requested_key
    else:
        path_hash, title = public_url_key_for_path(info_hash, path, torrent_name)

    set_fields = {
        "path": path,
        "title": title,
        "updated_at": datetime.now(),
    }
    if active:
        set_fields["active"] = True

    set_on_insert = {
        "user_id": user_id,
        "info_hash": info_hash,
        "path_hash": path_hash,
        "created_at": datetime.now(),
    }
    if not active:
        set_on_insert["active"] = False

    await db.public_urls.update_one(
        {"user_id": user_id, "info_hash": info_hash, "path_hash": path_hash},
        {
            "$set": set_fields,
            "$setOnInsert": set_on_insert,
        },
        upsert=True,
    )
    return title


@router.post("/generate-public-url")
async def generate_public_url(payload: Payload, request: Request):
    user_id = authenticate_user(request)
    path_user_id = payload.path.split("/")[2]
    info_hash = payload.path.split("/")[3]

    if path_user_id != user_id.decode():
        raise HTTPException(status_code=403, detail="Access denied")

    if not os.path.exists(payload.path):
        raise HTTPException(status_code=404, detail="Path not found")

    title = await ensure_public_url_record(
        user_id.decode(),
        info_hash,
        payload.path,
        active=True,
        key=payload.key,
    )

    return {"key": title}


@router.get("/public-urls")
async def list_public_urls(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    user_id = authenticate_user(request).decode()
    filter_query = {"user_id": user_id, "active": True}
    total = await db.public_urls.count_documents(filter_query)
    cursor = db.public_urls.find(
        filter_query,
        {"_id": False},
    ).sort("updated_at", -1).skip((page - 1) * page_size).limit(page_size)

    items = []
    async for doc in cursor:
        if os.path.exists(doc.get("path") or ""):
            items.append(public_url_document(doc))

    return {"data": items, "meta": {"page": page, "page_size": page_size, "total": total}}


@router.patch("/public-urls/deactivate")
async def bulk_deactivate_public_urls(
    payload: PublicUrlBulkDeactivatePayload,
    request: Request,
):
    user_id = authenticate_user(request).decode()
    filter_query = {"user_id": user_id, "active": True}

    if not payload.all:
        path_hashes = [
            str(path_hash)
            for path_hash in (payload.path_hashes or [])
            if str(path_hash).strip()
        ]
        if not path_hashes:
            raise HTTPException(status_code=400, detail="No public URLs selected")
        filter_query["path_hash"] = {"$in": path_hashes}

    result = await db.public_urls.update_many(
        filter_query,
        {"$set": {"active": False, "updated_at": datetime.now()}},
    )

    return {"status": "success", "updated": result.modified_count}


@router.patch("/public-urls/{path_hash}/deactivate")
async def deactivate_public_url(path_hash: str, request: Request):
    user_id = authenticate_user(request).decode()
    result = await db.public_urls.update_one(
        {"user_id": user_id, "path_hash": path_hash, "active": True},
        {"$set": {"active": False, "updated_at": datetime.now()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Public URL not found")

    return {"status": "success"}


@router.get("/public/{key}")
async def public_file_access(request: Request, key: str, download: str = "false"):
    path = await db.public_urls.find_one(
        {
            "$or": [
                {"title": key},
                {"path_hash": key},
            ],
            "active": True,
        }
    )
    if not path:
        raise HTTPException(status_code=404, detail="Public URL not found")

    path = path.get("path")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")

    download = download == "true" or download == "1"
    return handle_stream_file(request, path, download)
