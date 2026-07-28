import os
import re
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import requests
from bson import ObjectId
from pymongo import MongoClient

from shared.env import (
    MONGO_DATABASE_NAME,
    MONGO_DATABASE_URI,
    TMDB_API_KEY,
    TMDB_LANGUAGE,
    TMDB_READ_ACCESS_TOKEN,
)
from shared.modules.torrent_name_parser import parse

DOWNLOAD_ROOT = Path(os.getenv("DOWNLOAD_PATH", "/downloads"))
VIDEO_EXTENSIONS = {"mp4", "mkv", "avi", "mov", "wmv", "flv", "webm", "m4v"}
TMDB_API_ROOT = "https://api.themoviedb.org/3"
TMDB_IMAGE_ROOT = "https://image.tmdb.org/t/p"
IMDB_SUGGEST_ROOT = "https://v3.sg.media-imdb.com/suggestion/x"
_REFRESH_IN_FLIGHT = {}
_REFRESH_SUCCESS_COOLDOWN_SECONDS = 15 * 60
_REFRESH_FAILURE_COOLDOWN_SECONDS = 60


def _torrent_identifier(torrent):
    return str(
        torrent.get("info_hash")
        or torrent.get("url_hash")
        or torrent.get("_id")
        or ""
    )


def _safe_relative_path(path: Path):
    try:
        return path.resolve().relative_to(DOWNLOAD_ROOT.resolve()).as_posix()
    except ValueError:
        return None


def _is_video_path(path: Path):
    return path.is_file() and path.suffix.lower().lstrip(".") in VIDEO_EXTENSIONS


def _clean_title(value):
    value = re.sub(r"[._]+", " ", str(value or ""))
    value = re.sub(r"\s+", " ", value)
    return value.strip(" -")


def parse_media_name(name):
    parsed = {}
    try:
        parsed = parse(Path(name).stem)
    except Exception:
        parsed = {}

    title = _clean_title(parsed.get("title") or Path(name).stem)
    year = parsed.get("year")
    if isinstance(year, list):
        year = year[0] if year else None

    return {
        "title": title,
        "year": int(year) if str(year or "").isdigit() else None,
        "resolution": parsed.get("resolution"),
        "source": parsed.get("quality") or parsed.get("source"),
        "codec": parsed.get("codec"),
        "audio": parsed.get("audio"),
        "season": parsed.get("season"),
        "episode": parsed.get("episode"),
    }


def _first_int(value):
    if isinstance(value, list):
        value = value[0] if value else None
    return int(value) if str(value or "").isdigit() else None


def _parsed_media_type(parsed):
    return "tv" if parsed.get("season") or parsed.get("episode") else "movie"


def _tmdb_headers():
    headers = {"Accept": "application/json"}
    if TMDB_READ_ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {TMDB_READ_ACCESS_TOKEN}"
    return headers


def _tmdb_params(params):
    output = dict(params)
    if TMDB_API_KEY and not TMDB_READ_ACCESS_TOKEN:
        output["api_key"] = TMDB_API_KEY
    return output


def _tmdb_enabled():
    return bool(TMDB_API_KEY or TMDB_READ_ACCESS_TOKEN)


def _request_tmdb(path, params):
    if not _tmdb_enabled():
        return None

    response = requests.get(
        f"{TMDB_API_ROOT}{path}",
        headers=_tmdb_headers(),
        params=_tmdb_params(params),
        timeout=8,
    )
    response.raise_for_status()
    return response.json()


def _search_movie(title, year=None):
    if not title:
        return None

    params = {
        "query": title,
        "include_adult": "false",
        "language": TMDB_LANGUAGE,
        "page": 1,
    }
    if year:
        params["year"] = year
        params["primary_release_year"] = year

    data = _request_tmdb("/search/movie", params)
    results = (data or {}).get("results") or []
    if not results and year:
        params.pop("year", None)
        params.pop("primary_release_year", None)
        data = _request_tmdb("/search/movie", params)
        results = (data or {}).get("results") or []

    return results[0] if results else None


def _search_tv(title, year=None):
    if not title:
        return None

    params = {
        "query": title,
        "include_adult": "false",
        "language": TMDB_LANGUAGE,
        "page": 1,
    }
    if year:
        params["first_air_date_year"] = year

    data = _request_tmdb("/search/tv", params)
    results = (data or {}).get("results") or []
    if not results and year:
        params.pop("first_air_date_year", None)
        data = _request_tmdb("/search/tv", params)
        results = (data or {}).get("results") or []

    exact = str(title).strip().lower()
    for result in results:
        names = [result.get("name"), result.get("original_name")]
        if any(str(name or "").strip().lower() == exact for name in names):
            return result

    return results[0] if results else None


def _movie_details(movie_id):
    if not movie_id:
        return None

    try:
        return _request_tmdb(
            f"/movie/{movie_id}",
            {"append_to_response": "external_ids", "language": TMDB_LANGUAGE},
        )
    except Exception:
        return None


def _tv_details(tv_id):
    if not tv_id:
        return None

    try:
        return _request_tmdb(
            f"/tv/{tv_id}",
            {"append_to_response": "external_ids", "language": TMDB_LANGUAGE},
        )
    except Exception:
        return None


def _imdb_url(imdb_id):
    if not imdb_id:
        return None

    imdb_id = str(imdb_id).strip()
    if not imdb_id:
        return None

    return f"https://www.imdb.com/title/{imdb_id}/"


def _ensure_imdb_url_cached(db, doc):
    if not doc or doc.get("imdb_url"):
        return doc

    imdb_id = doc.get("imdb_id")
    if not imdb_id and doc.get("tmdb_id"):
        details = _movie_details(doc.get("tmdb_id")) or {}
        imdb_id = (details.get("external_ids") or {}).get("imdb_id")

    imdb_url = _imdb_url(imdb_id)
    if not imdb_url:
        return doc

    db.movie_metadata.update_one(
        {"_id": doc["_id"]},
        {
            "$set": {
                "imdb_id": imdb_id,
                "imdb_url": imdb_url,
                "updated_at": datetime.utcnow(),
            }
        },
    )
    doc["imdb_id"] = imdb_id
    doc["imdb_url"] = imdb_url
    return doc


def _download_poster(path):
    if not path:
        return None, None, None

    poster_url = f"{TMDB_IMAGE_ROOT}/w500{path}"
    response = requests.get(poster_url, timeout=12)
    response.raise_for_status()
    content_type = response.headers.get("content-type") or "image/jpeg"
    return poster_url, content_type, response.content


def _download_image_url(url):
    if not url:
        return None, None, None

    response = requests.get(url, timeout=12)
    response.raise_for_status()
    content_type = response.headers.get("content-type") or "image/jpeg"
    return url, content_type, response.content


def _search_imdb_suggestion(title, year=None):
    if not title:
        return None

    response = requests.get(
        f"{IMDB_SUGGEST_ROOT}/{quote(str(title).lower())}.json",
        timeout=8,
    )
    response.raise_for_status()
    results = response.json().get("d") or []
    movie_results = [
        result
        for result in results
        if result.get("qid") in {"movie", "tvMovie"}
        or result.get("q") in {"feature", "TV movie"}
    ]
    if not movie_results:
        movie_results = results

    if year:
        for result in movie_results:
            if str(result.get("y") or "") == str(year):
                return result

    return movie_results[0] if movie_results else None


def _search_imdb_suggestion_tv(title, year=None):
    if not title:
        return None

    response = requests.get(
        f"{IMDB_SUGGEST_ROOT}/{quote(str(title).lower())}.json",
        timeout=8,
    )
    response.raise_for_status()
    results = response.json().get("d") or []
    tv_results = [
        result
        for result in results
        if result.get("qid") in {"tvSeries", "tvMiniSeries", "tvShort"}
        or result.get("q") in {"TV series", "TV mini-series", "TV short"}
    ]
    if not tv_results:
        tv_results = results

    exact = str(title).strip().lower()
    for result in tv_results:
        if str(result.get("l") or "").strip().lower() == exact:
            if not year or str(result.get("y") or "") == str(year):
                return result

    if year:
        for result in tv_results:
            if str(result.get("y") or "") == str(year):
                return result

    return tv_results[0] if tv_results else None


def _tmdb_search_metadata(parsed):
    title = parsed.get("title")
    year = parsed.get("year")
    media_type = _parsed_media_type(parsed)
    result = _search_tv(title, year) if media_type == "tv" else _search_movie(title, year)
    if not result and media_type == "tv":
        result = _search_movie(title, year)
        media_type = "movie" if result else "tv"
    if not result:
        return None

    if media_type == "tv":
        details = _tv_details(result.get("id")) or {}
        imdb_id = (details.get("external_ids") or {}).get("imdb_id")
        poster_url, poster_mime, poster_bytes = _download_poster(result.get("poster_path"))
        first_air_date = result.get("first_air_date") or ""
        return {
            "lookup_status": "matched",
            "media_type": "tv",
            "tmdb_id": result.get("id"),
            "imdb_id": imdb_id,
            "imdb_url": _imdb_url(imdb_id),
            "title": result.get("name") or parsed.get("title"),
            "original_title": result.get("original_name"),
            "year": int(first_air_date[:4]) if first_air_date[:4].isdigit() else parsed.get("year"),
            "overview": result.get("overview"),
            "vote_average": result.get("vote_average"),
            "poster_path": result.get("poster_path"),
            "poster_source_url": poster_url,
            "poster_mime": poster_mime,
            "poster_bytes": poster_bytes,
            "season": _first_int(parsed.get("season")),
            "episode": _first_int(parsed.get("episode")),
        }

    details = _movie_details(result.get("id")) or {}
    imdb_id = (details.get("external_ids") or {}).get("imdb_id")
    poster_url, poster_mime, poster_bytes = _download_poster(result.get("poster_path"))
    release_date = result.get("release_date") or ""
    return {
        "lookup_status": "matched",
        "media_type": "movie",
        "tmdb_id": result.get("id"),
        "imdb_id": imdb_id,
        "imdb_url": _imdb_url(imdb_id),
        "title": result.get("title") or parsed.get("title"),
        "original_title": result.get("original_title"),
        "year": int(release_date[:4]) if release_date[:4].isdigit() else parsed.get("year"),
        "overview": result.get("overview"),
        "vote_average": result.get("vote_average"),
        "poster_path": result.get("poster_path"),
        "poster_source_url": poster_url,
        "poster_mime": poster_mime,
        "poster_bytes": poster_bytes,
    }


def _imdb_search_metadata(parsed):
    title = parsed.get("title")
    year = parsed.get("year")
    media_type = _parsed_media_type(parsed)
    result = (
        _search_imdb_suggestion_tv(title, year)
        if media_type == "tv"
        else _search_imdb_suggestion(title, year)
    )
    image_url = ((result or {}).get("i") or {}).get("imageUrl")
    if not result or not image_url:
        return None

    poster_url, poster_mime, poster_bytes = _download_image_url(image_url)
    update = {
        "lookup_status": "matched",
        "media_type": media_type,
        "imdb_id": result.get("id"),
        "imdb_url": _imdb_url(result.get("id")),
        "title": result.get("l") or parsed.get("title"),
        "year": result.get("y") or parsed.get("year"),
        "poster_source_url": poster_url,
        "poster_mime": poster_mime,
        "poster_bytes": poster_bytes,
    }
    if media_type == "tv":
        update["season"] = _first_int(parsed.get("season"))
        update["episode"] = _first_int(parsed.get("episode"))
    return update


def _existing_metadata_still_valid(existing, parsed):
    if not existing or existing.get("lookup_status") != "matched" or not existing.get("poster_bytes"):
        return False

    desired_media_type = _parsed_media_type(parsed)
    if existing.get("media_type") != desired_media_type:
        return False

    if desired_media_type != "tv":
        return True

    parsed_title = str(parsed.get("title") or "").strip().lower()
    existing_title = str(existing.get("title") or "").strip().lower()
    return not parsed_title or existing_title == parsed_title


def _public_metadata_still_valid(metadata, parsed):
    if not metadata or not metadata.get("poster_url") or not metadata.get("imdb_url"):
        return False

    desired_media_type = _parsed_media_type(parsed)
    if metadata.get("media_type") != desired_media_type:
        return False

    if desired_media_type != "tv":
        return True

    parsed_title = str(parsed.get("title") or "").strip().lower()
    metadata_title = str(metadata.get("title") or "").strip().lower()
    return not parsed_title or metadata_title == parsed_title


def _poster_cache_version(doc):
    updated_at = doc.get("updated_at")
    if hasattr(updated_at, "timestamp"):
        return str(int(updated_at.timestamp()))
    return str(doc.get("_id") or "")


def _public_metadata(doc):
    if not doc:
        return None

    metadata_id = str(doc.get("_id")) if doc.get("_id") else None
    has_poster = bool(
        doc.get("poster_bytes") or doc.get("poster_mime") or doc.get("poster_source_url")
    )
    poster_url = None
    if has_poster and metadata_id:
        poster_url = f"/api/files/media-poster/{metadata_id}?v={_poster_cache_version(doc)}"

    return {
        "id": metadata_id,
        "media_type": doc.get("media_type"),
        "title": doc.get("title"),
        "original_title": doc.get("original_title"),
        "year": doc.get("year"),
        "overview": doc.get("overview"),
        "vote_average": doc.get("vote_average"),
        "runtime": doc.get("runtime"),
        "poster_url": poster_url,
        "tmdb_id": doc.get("tmdb_id"),
        "imdb_id": doc.get("imdb_id"),
        "imdb_url": doc.get("imdb_url") or _imdb_url(doc.get("imdb_id")),
        "quality": doc.get("quality") or {},
        "matched": bool(doc.get("tmdb_id") or doc.get("imdb_id")),
    }


def public_metadata(doc):
    return _public_metadata(doc)


def cache_media_metadata_for_path_sync(db, user_id, path: Path, torrent=None):
    if not _is_video_path(path):
        return None

    relative_path = _safe_relative_path(path)
    if not relative_path:
        return None

    torrent = torrent or {}
    torrent_id = _torrent_identifier(torrent)
    parsed = parse_media_name(path.name)
    existing = db.movie_metadata.find_one(
        {"user_id": str(user_id), "relative_path": relative_path}
    )
    if _existing_metadata_still_valid(existing, parsed):
        return _ensure_imdb_url_cached(db, existing)

    doc = {
        "user_id": str(user_id),
        "torrent_id": torrent_id,
        "relative_path": relative_path,
        "file_name": path.name,
        "file_size": path.stat().st_size if path.exists() else 0,
        "media_type": _parsed_media_type(parsed),
        "title": parsed.get("title"),
        "year": parsed.get("year"),
        "season": _first_int(parsed.get("season")),
        "episode": _first_int(parsed.get("episode")),
        "quality": {
            "resolution": parsed.get("resolution"),
            "source": parsed.get("source"),
            "codec": parsed.get("codec"),
            "audio": parsed.get("audio"),
        },
        "lookup_status": "local",
        "updated_at": datetime.utcnow(),
    }

    matched = False
    try:
        metadata = _tmdb_search_metadata(parsed)
        if metadata:
            doc.update(metadata)
            matched = True
    except Exception:
        doc["lookup_status"] = "failed" if _tmdb_enabled() else "local"

    if not matched:
        try:
            metadata = _imdb_search_metadata(parsed)
            if metadata:
                doc.update(metadata)
                matched = True
        except Exception:
            if doc.get("lookup_status") != "matched":
                doc["lookup_status"] = "failed"

    db.movie_metadata.update_one(
        {"user_id": str(user_id), "relative_path": relative_path},
        {"$set": doc, "$setOnInsert": {"created_at": datetime.utcnow()}},
        upsert=True,
    )
    return db.movie_metadata.find_one(
        {"user_id": str(user_id), "relative_path": relative_path}
    )


def cache_media_metadata_for_torrent_name_sync(db, user_id, torrent):
    torrent_id = _torrent_identifier(torrent)
    name = torrent.get("name") or torrent_id
    if not torrent_id or not name:
        return None

    existing = db.movie_metadata.find_one(
        {
            "user_id": str(user_id),
            "torrent_id": torrent_id,
            "source": "torrent_name",
        }
    )
    parsed = parse_media_name(name)
    if _existing_metadata_still_valid(existing, parsed):
        return _ensure_imdb_url_cached(db, existing)

    doc = {
        "user_id": str(user_id),
        "torrent_id": torrent_id,
        "relative_path": f"__torrent__/{torrent_id}",
        "file_name": name,
        "file_size": int(torrent.get("total_bytes") or 0),
        "media_type": _parsed_media_type(parsed),
        "source": "torrent_name",
        "title": parsed.get("title"),
        "year": parsed.get("year"),
        "season": _first_int(parsed.get("season")),
        "episode": _first_int(parsed.get("episode")),
        "quality": {
            "resolution": parsed.get("resolution"),
            "source": parsed.get("source"),
            "codec": parsed.get("codec"),
            "audio": parsed.get("audio"),
        },
        "lookup_status": "local",
        "updated_at": datetime.utcnow(),
    }

    matched = False
    try:
        metadata = _tmdb_search_metadata(parsed)
        if metadata:
            doc.update(metadata)
            matched = True
    except Exception:
        doc["lookup_status"] = "failed" if _tmdb_enabled() else "local"

    if not matched:
        try:
            metadata = _imdb_search_metadata(parsed)
            if metadata:
                doc.update(metadata)
                matched = True
        except Exception:
            if doc.get("lookup_status") != "matched":
                doc["lookup_status"] = "failed"

    db.movie_metadata.update_one(
        {
            "user_id": str(user_id),
            "torrent_id": torrent_id,
            "source": "torrent_name",
        },
        {"$set": doc, "$setOnInsert": {"created_at": datetime.utcnow()}},
        upsert=True,
    )
    return db.movie_metadata.find_one(
        {
            "user_id": str(user_id),
            "torrent_id": torrent_id,
            "source": "torrent_name",
        }
    )


def cache_torrent_media_metadata_sync(db, user_id, torrent):
    matched_count = 0
    if cache_media_metadata_for_torrent_name_sync(db, user_id, torrent):
        matched_count += 1

    save_dir = torrent.get("save_dir")
    if not save_dir:
        torrent_id = _torrent_identifier(torrent)
        if torrent_id:
            save_dir = DOWNLOAD_ROOT / str(user_id) / torrent_id

    root_path = Path(save_dir) if save_dir else None
    if not root_path or not root_path.exists():
        return matched_count

    paths = [root_path] if _is_video_path(root_path) else []
    if root_path.is_dir():
        paths.extend(path for path in root_path.rglob("*") if _is_video_path(path))

    count = matched_count
    for path in paths:
        if cache_media_metadata_for_path_sync(db, user_id, path, torrent):
            count += 1
    return count


def _sync_db():
    mongo_client = MongoClient(MONGO_DATABASE_URI)
    return mongo_client[MONGO_DATABASE_NAME]


def schedule_torrent_media_metadata_refresh(user_id, torrents):
    candidates = [
        torrent
        for torrent in torrents
        if not _public_metadata_still_valid(
            torrent.get("media_metadata") or {},
            parse_media_name(torrent.get("name") or _torrent_identifier(torrent)),
        )
        and (torrent.get("save_dir") or torrent.get("name"))
    ]
    if not candidates:
        return

    now = time.time()
    keys = [_torrent_identifier(torrent) for torrent in candidates]
    candidates = [
        torrent
        for torrent, key in zip(candidates, keys)
        if key and _REFRESH_IN_FLIGHT.get(f"{user_id}:{key}", 0) < now
    ]
    if not candidates:
        return

    for torrent in candidates:
        _REFRESH_IN_FLIGHT[f"{user_id}:{_torrent_identifier(torrent)}"] = (
            now + _REFRESH_SUCCESS_COOLDOWN_SECONDS
        )

    def _refresh():
        db = _sync_db()
        for torrent in candidates:
            try:
                cache_torrent_media_metadata_sync(db, user_id, torrent)
                torrent_id = _torrent_identifier(torrent)
                metadata = db.movie_metadata.find_one(
                    {
                        "user_id": str(user_id),
                        "torrent_id": torrent_id,
                    },
                    sort=[("file_size", -1)],
                )
                public = _public_metadata(metadata)
                if public:
                    from shared.sockets import emit

                    payload = {
                        "info_hash": torrent.get("info_hash"),
                        "url_hash": torrent.get("url_hash"),
                        "media_metadata": public,
                    }
                    emit(f"/stc/torrent-props-update/{torrent_id}", payload, user_id)
            except Exception:
                torrent_id = _torrent_identifier(torrent)
                _REFRESH_IN_FLIGHT[f"{user_id}:{torrent_id}"] = (
                    time.time() + _REFRESH_FAILURE_COOLDOWN_SECONDS
                )
                print(f"Media metadata refresh failed for {torrent_id}")
                traceback.print_exc()

    threading.Thread(target=_refresh, daemon=True).start()


async def attach_media_metadata(db, user_id, items):
    if not items:
        return items

    torrent_ids = [_torrent_identifier(item) for item in items]
    cursor = db.movie_metadata.find(
        {
            "user_id": str(user_id),
            "torrent_id": {"$in": [torrent_id for torrent_id in torrent_ids if torrent_id]},
        },
        {"poster_bytes": False},
    ).sort("file_size", -1)
    docs = await cursor.to_list(length=None)

    by_torrent = {}
    for doc in docs:
        by_torrent.setdefault(doc.get("torrent_id"), doc)

    for item in items:
        metadata = by_torrent.get(_torrent_identifier(item))
        if metadata:
            item["media_metadata"] = _public_metadata(metadata)
    return items


async def media_metadata_for_relative_paths(db, user_id, relative_paths):
    cursor = db.movie_metadata.find(
        {"user_id": str(user_id), "relative_path": {"$in": relative_paths}},
        {"poster_bytes": False},
    )
    docs = await cursor.to_list(length=None)
    return {doc.get("relative_path"): _public_metadata(doc) for doc in docs}


async def media_metadata_for_torrent_ids(db, user_id, torrent_ids):
    cursor = db.movie_metadata.find(
        {"user_id": str(user_id), "torrent_id": {"$in": torrent_ids}},
        {"poster_bytes": False},
    ).sort("file_size", -1)
    docs = await cursor.to_list(length=None)
    results = {}
    for doc in docs:
        results.setdefault(doc.get("torrent_id"), _public_metadata(doc))
    return results


async def delete_media_metadata_for_paths(db, user_id, relative_paths):
    if not relative_paths:
        return
    await db.movie_metadata.delete_many(
        {"user_id": str(user_id), "relative_path": {"$in": relative_paths}}
    )


async def delete_media_metadata_for_torrent(db, user_id, torrent_id):
    if not torrent_id:
        return
    await db.movie_metadata.delete_many(
        {"user_id": str(user_id), "torrent_id": str(torrent_id)}
    )


async def get_poster_document(db, user_id, metadata_id):
    try:
        object_id = ObjectId(metadata_id)
    except Exception:
        return None
    return await db.movie_metadata.find_one(
        {"_id": object_id, "user_id": str(user_id)},
        {"poster_bytes": True, "poster_mime": True},
    )
