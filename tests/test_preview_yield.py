"""A foreground playback signal interrupts and reaps an active preview child."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

spec=importlib.util.spec_from_file_location('preview_sprites',Path(__file__).resolve().parents[1]/'api/shared/modules/preview_sprites.py')
preview=importlib.util.module_from_spec(spec);spec.loader.exec_module(preview)

class PreviewYield(unittest.TestCase):
    def test_active_child_stops_for_playback(self):
        with tempfile.TemporaryDirectory() as folder:
            marker=Path(folder)/'started'
            command=[sys.executable,'-c','import pathlib,time;pathlib.Path(__import__("sys").argv[1]).write_text("ready");time.sleep(10)',str(marker)]
            child=[]
            original=preview.subprocess.Popen
            def capture(*args,**kwargs):
                p=original(*args,**kwargs);child.append(p);return p
            preview.subprocess.Popen=capture
            def foreground():
                if marker.exists():raise RuntimeError('Playback active')
            started=time.monotonic()
            try:
                with self.assertRaisesRegex(RuntimeError,'Playback active'):
                    preview._run_idle(command,foreground,12)
            finally:preview.subprocess.Popen=original
            self.assertLess(time.monotonic()-started,2)
            self.assertIsNotNone(child[0].returncode)
            self.assertIsNotNone(child[0].poll())

    def test_deadline_is_bounded(self):
        started=time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            preview._run_idle([sys.executable,'-c','import time;time.sleep(10)'],lambda:None,.15)
        self.assertLess(time.monotonic()-started,2)

    def test_idle_output_and_failure_are_preserved(self):
        result=preview._run_idle([sys.executable,'-c','print("frame")'],lambda:None,2)
        self.assertEqual(result.stdout,b'frame\n');self.assertEqual(result.returncode,0)
        result=preview._run_idle([sys.executable,'-c','raise SystemExit(3)'],lambda:None,2)
        self.assertEqual(result.returncode,3)

if __name__=='__main__':unittest.main()
