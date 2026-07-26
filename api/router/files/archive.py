import os
import json
import subprocess
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, HTTPException, Request

from ..auth.common import authenticate_user
from shared.factory import redis
from tasks.archive import archive_directory as archive_directory_task
from tasks.archive import extract_archive


router = APIRouter()


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _user_path(path: str, user_id: str) -> Path:
    """Resolve a UI path and ensure it stays in the authenticated user's files."""
    downloads = Path(os.getenv("DOWNLOAD_PATH", "/downloads")).resolve()
    user_root = (downloads / user_id).resolve()
    candidate = (downloads / path.lstrip("/")).resolve()
    if not _is_within(candidate, user_root):
        raise HTTPException(status_code=403, detail="Access denied")
    return candidate


def _extraction_dir(archive: Path) -> Path:
    # Treat common multi-part archive extensions as one extension.
    name = archive.name
    for suffix in (".tar.gz", ".tar.bz2", ".tar.xz", ".tar.zst"):
        if name.lower().endswith(suffix):
            return archive.with_name(name[: -len(suffix)])
    return archive.with_suffix("") if archive.suffix else archive.with_name(f"{name}-extracted")


def _archive_root_directory(archive: Path):
    """Return the sole root directory, but only when the archive has no loose files."""
    try:
        listing = subprocess.run(
            ["7z", "l", "-slt", str(archive)],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise HTTPException(status_code=400, detail=f"Unable to inspect archive: {exc}")

    entries = []
    for block in listing.split("----------", 1)[-1].split("\n\n"):
        fields = dict(
            line.split(" = ", 1) for line in block.splitlines() if " = " in line
        )
        if "Path" in fields:
            entries.append(fields)

    root_dirs = set()
    top_levels = set()
    has_nested_entry = False
    for entry in entries:
        path = PurePosixPath(entry["Path"].replace("\\", "/"))
        if path.is_absolute() or not path.parts or any(part in (".", "..") for part in path.parts):
            return None
        top_levels.add(path.parts[0])
        has_nested_entry = has_nested_entry or len(path.parts) > 1
        if len(path.parts) == 1 and entry.get("Folder") == "+":
            root_dirs.add(path.parts[0])

    # ZIPs often omit the directory entry and list only `directory/file`.
    # A nested entry proves that the single root is a directory, not a loose file.
    if len(top_levels) == 1 and (len(root_dirs) == 1 or has_nested_entry):
        return next(iter(top_levels))
    return None


@router.post("/archive")
async def archive_directory(path: str, request: Request):
    user_id = authenticate_user(request).decode()
    directory = _user_path(path, user_id)
    if not directory.exists():
        raise HTTPException(status_code=404, detail="Directory not found")
    if not directory.is_dir():
        raise HTTPException(status_code=400, detail="Only directories can be archived")

    archive_path = directory.parent / f"{directory.name}.zip"
    if archive_path.exists():
        raise HTTPException(status_code=409, detail="Archive already exists")

    key = f"archive_progress/{directory}"
    redis.set(key, '{"progress": 0, "status": "queued"}', ex=3600)
    result = archive_directory_task.delay(str(directory), str(archive_path), key)
    return {"task_id": result.task_id, "archive_path": str(archive_path)}


@router.post("/extract")
async def extract(path: str, request: Request):
    user_id = authenticate_user(request).decode()
    archive = _user_path(path, user_id)
    if not archive.exists():
        raise HTTPException(status_code=404, detail="Archive not found")
    if not archive.is_file():
        raise HTTPException(status_code=400, detail="Only files can be extracted")

    archive_root = _archive_root_directory(archive)
    output_dir = archive.parent / archive_root if archive_root else _extraction_dir(archive)
    if output_dir.exists():
        raise HTTPException(
            status_code=409, detail="The extraction directory already exists"
        )

    # Always extract into an isolated staging directory. Archives with one root
    # directory are moved beside the archive only after a successful extraction.
    staging_dir = (
        archive.with_name(f".{archive.name}.extracting") if archive_root else output_dir
    )
    try:
        staging_dir.mkdir(mode=0o755)
    except FileExistsError:
        raise HTTPException(
            status_code=409, detail="The extraction directory already exists"
        )
    key = f"archive_progress/{archive}"
    redis.set(key, '{"progress": 0, "status": "queued"}', ex=3600)
    result = extract_archive.delay(
        str(archive), str(staging_dir), key, str(output_dir) if archive_root else None
    )
    return {"task_id": result.task_id, "output_path": str(output_dir)}


@router.get("/archive/progress")
async def archive_progress(path: str, request: Request):
    user_id = authenticate_user(request).decode()
    item = _user_path(path, user_id)
    data = redis.get(f"archive_progress/{item}")
    if not data:
        return {"status": "unknown", "progress": 0}
    return json.loads(data)
