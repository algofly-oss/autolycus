from fastapi import APIRouter, Query, Request
from bson import ObjectId

from shared.modules.file_search_index import search_files
from shared.factory import db
from shared.modules.media_metadata import (
    media_metadata_for_relative_paths,
    media_metadata_for_torrent_ids,
)

from ..auth.common import authenticate_user

router = APIRouter()


def _public_torrent(torrent):
    return {
        key: value
        for key, value in torrent.items()
        if key not in {"_id", "user_id"}
    }


@router.get("/search")
async def search_downloaded_files(
    request: Request,
    q: str = Query("", max_length=200),
    item_type: str = Query("", max_length=20),
    extension: str = Query("", max_length=40),
    torrent_id: str = Query("", max_length=120),
    sort: str = Query("modified:desc", max_length=40),
    limit: int = Query(40, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    user_id = authenticate_user(request).decode("utf-8")
    response = await search_files(
        query=q,
        user_id=user_id,
        item_type=item_type or None,
        extension=extension or None,
        torrent_id=torrent_id or None,
        sort=sort or None,
        limit=limit,
        offset=offset,
    )
    hits = response.get("hits", [])
    path_media_metadata = await media_metadata_for_relative_paths(
        db,
        user_id,
        [hit.get("relative_path") for hit in hits if hit.get("relative_path")],
    )
    torrent_media_metadata = await media_metadata_for_torrent_ids(
        db,
        user_id,
        [hit.get("torrent_id") for hit in hits if hit.get("torrent_id")],
    )
    torrent_ids = [
        hit.get("torrent_id")
        for hit in hits
        if hit.get("is_torrent_root") and hit.get("torrent_id")
    ]
    live_torrents = {}
    if torrent_ids:
        torrent_cursor = db.torrents.find(
            {
                "user_id": ObjectId(user_id),
                "$or": [
                    {"info_hash": {"$in": torrent_ids}},
                    {"url_hash": {"$in": torrent_ids}},
                ],
            }
        )
        async for torrent in torrent_cursor:
            public_torrent = _public_torrent(torrent)
            for key in ("info_hash", "url_hash"):
                torrent_key = public_torrent.get(key)
                if torrent_key:
                    live_torrents[torrent_key] = public_torrent

    for hit in hits:
        live_torrent = live_torrents.get(hit.get("torrent_id"))
        if hit.get("is_torrent_root") and live_torrent:
            search_fields = {
                "id": hit.get("id"),
                "torrent_id": hit.get("torrent_id"),
                "item_type": hit.get("item_type"),
                "is_torrent_root": hit.get("is_torrent_root"),
                "relative_path": hit.get("relative_path"),
                "full_path": hit.get("full_path"),
                "directory_path": hit.get("directory_path"),
                "last_modified_ts": hit.get("last_modified_ts"),
            }
            hit.update(live_torrent)
            hit.update(search_fields)
            hit["size"] = int(hit.get("total_bytes") or hit.get("size") or 0)

        metadata = (
            torrent_media_metadata.get(hit.get("torrent_id"))
            or path_media_metadata.get(hit.get("relative_path"))
        )
        if metadata:
            hit["media_metadata"] = metadata
    return {
        "data": hits,
        "meta": {
            "estimated_total_hits": response.get("estimatedTotalHits", 0),
            "processing_time_ms": response.get("processingTimeMs", 0),
        },
    }
