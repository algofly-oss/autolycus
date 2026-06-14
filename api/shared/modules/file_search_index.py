import asyncio
import hashlib
import os
import time
import traceback
from pathlib import Path

from bson import ObjectId

from shared.env import MEILI_SEARCH_MAX_TOTAL_HITS
from shared.modules.meilisearch_client import meili

DOWNLOAD_ROOT = Path(os.getenv("DOWNLOAD_PATH", "/downloads"))


def _safe_stat(path: Path):
    try:
        return path.stat()
    except OSError:
        return None


def _torrent_identifier(torrent):
    return str(
        torrent.get("info_hash")
        or torrent.get("url_hash")
        or torrent.get("_id")
        or ""
    )


def _torrent_title(torrent):
    return str(torrent.get("name") or _torrent_identifier(torrent) or "").strip()


def _document_id(user_id, relative_path):
    raw = f"{user_id}:{relative_path}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


def torrent_root_document_id(user_id, torrent_id):
    return _document_id(user_id, f"{user_id}/{torrent_id}/__torrent_root__")


def _relative_path(path: Path):
    return path.resolve().relative_to(DOWNLOAD_ROOT.resolve()).as_posix()


def _quote_filter(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _root_path_for_torrent(user_id, torrent):
    save_dir = torrent.get("save_dir")
    if not save_dir:
        torrent_id = _torrent_identifier(torrent)
        if torrent_id:
            save_dir = DOWNLOAD_ROOT / str(user_id) / torrent_id

    root_path = Path(save_dir) if save_dir else None
    if not root_path:
        return None

    torrent_name_path = root_path / str(torrent.get("name") or "")
    if torrent_name_path.exists():
        return torrent_name_path

    return root_path


def _timestamp_for_torrent(torrent):
    for key in ("updated_at", "created_at"):
        value = torrent.get(key)
        if hasattr(value, "timestamp"):
            return int(value.timestamp())
    return int(time.time())


def _torrent_root_document(user_id, torrent):
    torrent_id = _torrent_identifier(torrent)
    torrent_title = _torrent_title(torrent)
    if not torrent_id or not torrent_title or torrent_title == "Unknown":
        return None

    relative_path = f"{user_id}/{torrent_id}/{torrent_title}"
    directory_path = f"{user_id}/{torrent_id}"
    return {
        "id": torrent_root_document_id(user_id, torrent_id),
        "user_id": str(user_id),
        "torrent_id": torrent_id,
        "torrent_title": torrent_title,
        "item_type": "directory",
        "is_torrent_root": True,
        "name": torrent_title,
        "stem": torrent_title,
        "extension": "",
        "relative_path": relative_path,
        "full_path": str((DOWNLOAD_ROOT / str(user_id) / torrent_id / torrent_title).resolve()),
        "directory_path": directory_path,
        "directory_names": [torrent_id],
        "size": int(torrent.get("total_bytes") or 0),
        "last_modified_ts": _timestamp_for_torrent(torrent),
        "content": " ".join(
            [
                torrent_title,
                relative_path,
                directory_path,
                "torrent",
                "directory",
            ]
        ),
    }


def _document_for_path(path: Path, user_id, torrent):
    stat = _safe_stat(path)
    if not stat:
        return None

    relative_path = _relative_path(path)
    directory_path = path.parent.resolve().relative_to(DOWNLOAD_ROOT.resolve()).as_posix()
    directory_names = [
        part
        for part in Path(directory_path).parts
        if part not in {"", ".", str(user_id)}
    ]
    name = path.name
    extension = path.suffix.lower().lstrip(".") if path.is_file() else ""
    item_type = "directory" if path.is_dir() else "file"
    torrent_title = _torrent_title(torrent)
    is_torrent_root = path.name == torrent_title or relative_path.endswith(
        f"/{_torrent_identifier(torrent)}/{torrent_title}"
    )
    size = stat.st_size if path.is_file() else 0
    if item_type == "directory" and is_torrent_root:
        size = int(torrent.get("total_bytes") or 0)

    return {
        "id": _document_id(user_id, relative_path),
        "user_id": str(user_id),
        "torrent_id": _torrent_identifier(torrent),
        "torrent_title": torrent_title,
        "item_type": item_type,
        "is_torrent_root": bool(is_torrent_root),
        "name": name,
        "stem": path.stem,
        "extension": extension,
        "relative_path": relative_path,
        "full_path": str(path.resolve()),
        "directory_path": directory_path,
        "directory_names": directory_names,
        "size": size,
        "last_modified_ts": int(stat.st_mtime),
        "content": " ".join(
            [
                torrent_title,
                name,
                path.stem,
                extension,
                relative_path,
                directory_path,
                " ".join(directory_names),
                item_type,
            ]
        ),
    }


def _documents_for_tree(root_path: Path, user_id, torrent):
    root_document = _torrent_root_document(user_id, torrent)
    if not root_path.exists():
        return [root_document] if root_document else []

    paths = []
    if root_path.is_dir():
        paths.extend(root_path.rglob("*"))
    else:
        paths.append(root_path)

    documents = []
    if root_document:
        documents.append(root_document)
    for path in paths:
        if path.exists() and (path.is_file() or path.is_dir()):
            document = _document_for_path(path, user_id, torrent)
            if document:
                documents.append(document)
    return documents


def document_ids_for_tree(root_path: Path, user_id):
    if not root_path.exists():
        return []

    paths = [root_path]
    if root_path.is_dir():
        paths.extend(root_path.rglob("*"))

    document_ids = []
    for path in paths:
        try:
            relative_path = _relative_path(path)
        except ValueError:
            continue
        document_ids.append(_document_id(user_id, relative_path))
    return document_ids


def _stale_torrent_root_document_ids(user_id, torrent, root_path=None):
    stale_ids = set()
    torrent_id = _torrent_identifier(torrent)
    torrent_title = _torrent_title(torrent)
    if torrent_id and torrent_title:
        stale_ids.add(_document_id(user_id, f"{user_id}/{torrent_id}/{torrent_title}"))

    if root_path and root_path.exists():
        try:
            stale_ids.add(_document_id(user_id, _relative_path(root_path)))
        except ValueError:
            pass

    stale_ids.discard(torrent_root_document_id(user_id, torrent_id))
    return list(stale_ids)


def index_torrent_root_sync(user_id, torrent):
    document = _torrent_root_document(str(user_id), torrent)
    if not document:
        return 0

    index = meili.ensure_file_index()
    if not index:
        return 0
    stale_ids = _stale_torrent_root_document_ids(str(user_id), torrent)
    if stale_ids:
        task = index.delete_documents(stale_ids)
        index.wait_for_task(task.task_uid, timeout_in_ms=60000)
    task = index.update_documents([document])
    index.wait_for_task(task.task_uid, timeout_in_ms=60000)
    return 1


async def index_torrent_root(user_id, torrent):
    return await asyncio.to_thread(index_torrent_root_sync, user_id, torrent)


def index_torrent_files_sync(user_id, torrent):
    root_path = _root_path_for_torrent(user_id, torrent)
    if not root_path:
        return index_torrent_root_sync(user_id, torrent)

    documents = _documents_for_tree(root_path, user_id, torrent)
    if not documents:
        return 0

    index = meili.ensure_file_index()
    if not index:
        return 0
    stale_ids = _stale_torrent_root_document_ids(str(user_id), torrent, root_path)
    if stale_ids:
        task = index.delete_documents(stale_ids)
        index.wait_for_task(task.task_uid, timeout_in_ms=60000)
    task = index.update_documents(documents)
    index.wait_for_task(task.task_uid, timeout_in_ms=60000)
    return len(documents)


async def index_torrent_files(user_id, torrent):
    return await asyncio.to_thread(index_torrent_files_sync, user_id, torrent)


def _indexed_document_ids_for_torrent(index, user_id, torrent_id, expected_count):
    if not torrent_id or expected_count <= 0:
        return set()

    limit = min(max(1, expected_count), MEILI_SEARCH_MAX_TOTAL_HITS)
    response = index.search(
        "",
        {
            "limit": limit,
            "filter": [
                f"user_id = {_quote_filter(user_id)}",
                f"torrent_id = {_quote_filter(torrent_id)}",
            ],
            "attributesToRetrieve": ["id"],
        },
    )
    return {hit.get("id") for hit in response.get("hits", []) if hit.get("id")}


def index_missing_torrent_files_sync(user_id, torrent):
    root_path = _root_path_for_torrent(user_id, torrent)
    if not root_path:
        return index_torrent_root_sync(user_id, torrent)

    expected_documents = _documents_for_tree(root_path, user_id, torrent)
    expected_document_ids = {doc.get("id") for doc in expected_documents if doc.get("id")}
    if not expected_document_ids:
        return 0

    index = meili.ensure_file_index()
    if not index:
        return 0

    torrent_id = _torrent_identifier(torrent)
    if len(expected_document_ids) <= MEILI_SEARCH_MAX_TOTAL_HITS:
        indexed_document_ids = _indexed_document_ids_for_torrent(
            index,
            str(user_id),
            torrent_id,
            len(expected_document_ids),
        )
        if expected_document_ids.issubset(indexed_document_ids):
            return 0

    return index_torrent_files_sync(user_id, torrent)


async def backfill_missing_search_index(db):
    indexed_count = 0
    checked_count = 0

    async for torrent in db.torrents.find({}):
        user_id = torrent.get("user_id")
        if not user_id:
            continue

        checked_count += 1
        indexed_count += await asyncio.to_thread(
            index_missing_torrent_files_sync,
            str(user_id),
            torrent,
        )

    return {"checked": checked_count, "indexed": indexed_count}


def schedule_missing_search_index_backfill(db):
    async def _run():
        try:
            result = await backfill_missing_search_index(db)
            print(
                "Search index startup backfill complete: "
                f"checked={result['checked']} indexed={result['indexed']}"
            )
        except Exception:
            traceback.print_exc()

    try:
        asyncio.get_running_loop().create_task(_run())
    except RuntimeError:
        pass


async def torrent_for_path(db, user_id, path: Path):
    try:
        relative_parts = path.resolve().relative_to(DOWNLOAD_ROOT.resolve()).parts
    except ValueError:
        return None

    if len(relative_parts) < 2 or relative_parts[0] != str(user_id):
        return None

    torrent_id = relative_parts[1]
    return await db.torrents.find_one(
        {
            "user_id": ObjectId(str(user_id)),
            "$or": [{"info_hash": torrent_id}, {"url_hash": torrent_id}],
        }
    )


async def index_path_for_user(db, user_id, path: Path):
    torrent = await torrent_for_path(db, user_id, path)
    if not torrent:
        return 0
    return await index_torrent_files(user_id, {**torrent, "save_dir": str(path)})


def delete_document_ids_sync(document_ids):
    document_ids = [document_id for document_id in document_ids if document_id]
    if not document_ids:
        return 0

    index = meili.ensure_file_index()
    if not index:
        return 0
    task = index.delete_documents(document_ids)
    index.wait_for_task(task.task_uid, timeout_in_ms=60000)
    return len(document_ids)


async def delete_document_ids(document_ids):
    return await asyncio.to_thread(delete_document_ids_sync, document_ids)


def delete_tree_from_index_sync(root_path: Path, user_id):
    return delete_document_ids_sync(document_ids_for_tree(root_path, user_id))


async def delete_tree_from_index(root_path: Path, user_id):
    return await asyncio.to_thread(delete_tree_from_index_sync, root_path, user_id)


async def search_files(
    query,
    user_id,
    item_type=None,
    extension=None,
    torrent_id=None,
    sort=None,
    limit=40,
    offset=0,
):
    index = await meili.ensure_file_index_async()
    if not index:
        return {"hits": [], "estimatedTotalHits": 0, "processingTimeMs": 0}

    filters = [f"user_id = {_quote_filter(user_id)}"]

    if item_type == "torrent":
        filters.append(f"item_type = {_quote_filter('directory')}")
        filters.append("is_torrent_root = true")
    elif item_type == "folder":
        filters.append(f"item_type = {_quote_filter('directory')}")
        filters.append("is_torrent_root = false")
    elif item_type == "all":
        filters.append("is_torrent_root = false")
    elif item_type in {"file", "directory"}:
        filters.append(f"item_type = {_quote_filter(item_type)}")
    if extension:
        filters.append(
            f"extension = {_quote_filter(str(extension).strip().lower().lstrip('.'))}"
        )
    if torrent_id:
        filters.append(f"torrent_id = {_quote_filter(torrent_id)}")

    search_options = {
        "limit": max(1, min(int(limit or 40), 100)),
        "offset": max(0, int(offset or 0)),
        "filter": filters,
        "attributesToRetrieve": [
            "id",
            "torrent_id",
            "torrent_title",
            "item_type",
            "is_torrent_root",
            "name",
            "extension",
            "relative_path",
            "full_path",
            "directory_path",
            "size",
            "last_modified_ts",
        ],
    }

    sort_map = {
        "name:asc": ["name:asc"],
        "name:desc": ["name:desc"],
        "size:asc": ["size:asc"],
        "size:desc": ["size:desc"],
        "modified:asc": ["last_modified_ts:asc"],
        "modified:desc": ["last_modified_ts:desc"],
    }
    if sort in sort_map:
        search_options["sort"] = sort_map[sort]

    return await asyncio.to_thread(
        index.search,
        str(query or ""),
        search_options,
    )
