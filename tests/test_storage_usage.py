"""Regression: shared app usage, outside-space subtraction and hard-link deduplication."""
import json
import os
import sys
import tempfile
import unittest
from collections import namedtuple
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'api'))
from shared.modules.storage_usage import allocated_bytes, get_disk_usage, refresh_storage_usage


class DriveUsageTests(unittest.TestCase):
    def test_users_share_app_usage_and_capacity_excludes_other_directories(self):
        drive = namedtuple('usage', 'total used free')(8000, 1500, 6400)
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / 'usage.json'
            cache.write_text(json.dumps({'used': 300}))
            with patch('shared.modules.storage_usage.CACHE', cache), patch('shared.modules.storage_usage.shutil.disk_usage', return_value=drive):
                expected = {'used': 300, 'total': 6800, 'free': 6400}
                self.assertEqual(get_disk_usage('new-user'), expected)
                self.assertEqual(get_disk_usage('existing-user'), expected)

    def test_hardlinks_and_overlapping_roots_are_counted_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = root / 'payload'
            payload.write_bytes(b'x' * 8192)
            os.link(payload, root / 'friendly-name')
            expected = (root.stat().st_blocks + payload.stat().st_blocks) * 512
            self.assertEqual(allocated_bytes([root, root, payload], root.stat().st_dev), expected)

    def test_concurrent_refreshes_publish_complete_snapshots(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / 'usage.json'
            with patch.dict(os.environ, {'DOWNLOAD_PATH': directory}), patch('shared.modules.storage_usage.CACHE', cache):
                with ThreadPoolExecutor(max_workers=4) as pool:
                    samples = list(pool.map(lambda _: refresh_storage_usage(), range(16)))
                self.assertIn(json.loads(cache.read_text())['used'], samples)
                self.assertFalse(list(Path(directory).glob('.storage-usage-*')))


if __name__ == '__main__':
    unittest.main()
