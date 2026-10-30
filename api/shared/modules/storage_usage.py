"""Deduplicated installation usage, sampled outside request and progress paths."""
import json
import os
import shutil
import stat
import tempfile
from pathlib import Path

CACHE = Path(os.environ.get('AUTOLYCUS_STORAGE_CACHE', '/data/storage_usage.json'))


def allocated_bytes(roots, device):
    seen = set()
    pending = list(roots)
    occupied = 0
    while pending:
        path = pending.pop()
        try:
            entry = os.lstat(path)
            identity = (entry.st_dev, entry.st_ino)
            if entry.st_dev != device or identity in seen:
                continue
            seen.add(identity)
            occupied += entry.st_blocks * 512
            if stat.S_ISDIR(entry.st_mode):
                with os.scandir(path) as children:
                    pending.extend(child.path for child in children)
        except (FileNotFoundError, NotADirectoryError):
            # Downloads and temporary files can disappear during a sample.
            continue
    return occupied


def refresh_storage_usage():
    downloads = os.environ.get('DOWNLOAD_PATH', '/downloads')
    roots = [Path('/installation'), Path('/data'), Path(downloads)]
    occupied = allocated_bytes(roots, os.stat(downloads).st_dev)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=CACHE.parent, prefix='.storage-usage-', delete=False) as output:
        json.dump({'used': occupied}, output)
        temporary = Path(output.name)
    try:
        temporary.replace(CACHE)
    finally:
        temporary.unlink(missing_ok=True)
    return occupied


def get_disk_usage(user_id=None):
    # Shared installation usage, never an individual user's virtual quota.
    drive = shutil.disk_usage(os.environ.get('DOWNLOAD_PATH', '/downloads'))
    try:
        occupied = json.loads(CACHE.read_text())['used']
    except (FileNotFoundError, ValueError, KeyError):
        occupied = refresh_storage_usage()
    outside = max(0, drive.used - occupied)
    return {'used': occupied, 'total': drive.total - outside, 'free': drive.free}
