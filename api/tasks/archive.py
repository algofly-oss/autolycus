import json
import os
import re
import shutil
import subprocess
import time

import celery_worker
from shared.factory import redis


PROGRESS = re.compile(r"(\d{1,3})%")


def _update(key, progress, status="running", error=None, started_at=None):
    progress = min(100, max(0, progress))
    payload = {"progress": progress, "status": status, "eta": 0}
    if started_at and 0 < progress < 100:
        elapsed = time.monotonic() - started_at
        payload["eta"] = max(0, round(elapsed * (100 - progress) / progress))
    if error:
        payload["error"] = error
    redis.set(key, json.dumps(payload), ex=3600)


def _run_7zip(command, key, cwd=None, started_at=None):
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=cwd,
    )
    output = ""
    last_progress = None
    while True:
        chunk = process.stdout.read(1)
        if not chunk:
            break
        output += chunk
        matches = PROGRESS.findall(output)
        if matches:
            progress = int(matches[-1])
            if progress != last_progress:
                _update(key, progress, started_at=started_at)
                last_progress = progress
        # 7-Zip overwrites a single progress line rather than terminating it.
        # Retain only enough stream history to recognise the next percentage.
        output = output[-32:]
    return_code = process.wait()
    if return_code:
        raise RuntimeError(f"7-Zip exited with code {return_code}")


@celery_worker.app.task(queue="archive")
def archive_directory(source_path, archive_path, key):
    try:
        started_at = time.monotonic()
        _update(key, 0)
        # Match the existing ZIP behaviour: its contents are the archive root.
        _run_7zip(
            ["7z", "a", "-tzip", "-bsp1", archive_path, "."],
            key,
            cwd=source_path,
            started_at=started_at,
        )
        _update(key, 100, "complete")
        return {"message": "success", "archive_path": archive_path}
    except Exception as exc:
        if os.path.exists(archive_path):
            os.unlink(archive_path)
        _update(key, 0, "failed", str(exc))
        raise


@celery_worker.app.task(queue="archive")
def extract_archive(archive_path, staging_dir, key, final_path=None):
    try:
        started_at = time.monotonic()
        _update(key, 0)
        # -o is an explicit, pre-created staging directory, so archive paths never
        # write into the folder currently being viewed.
        _run_7zip(
            ["7z", "x", "-bsp1", f"-o{staging_dir}", archive_path],
            key,
            started_at=started_at,
        )
        if final_path:
            root_name = os.path.basename(final_path)
            os.replace(os.path.join(staging_dir, root_name), final_path)
            os.rmdir(staging_dir)
        _update(key, 100, "complete")
        return {"message": "success", "output_path": final_path or staging_dir}
    except Exception as exc:
        # Do not leave a partial extraction that looks complete to the user.
        if os.path.isdir(staging_dir):
            shutil.rmtree(staging_dir)
        _update(key, 0, "failed", str(exc))
        raise
