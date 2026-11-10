"""Opt-in TV density preserves legacy cache/PNG and yields while feeding an encoder."""
import ast
import asyncio
import importlib.util
import json
import math
import random
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('preview_detail', ROOT/'api/shared/modules/preview_sprites.py')
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


class DetailPreviews(unittest.TestCase):
    def test_density_and_decoded_bounds(self):
        self.assertEqual(preview.sample_count(78*60), 100)
        self.assertEqual(preview.sample_count(78*60, True), 936)
        self.assertEqual(preview.sample_count(20000, True), 1000)
        for duration in (0.1, 2, 5, 15, 100, 4680, 20000):
            count = preview.sample_count(duration, True)
            columns = min(25, count)
            pixels = columns*160*math.ceil(count/columns)*90
            self.assertLessEqual(pixels, 14_400_000)
            self.assertLessEqual(columns*160,4096)
            self.assertLessEqual(math.ceil(count/columns)*90,4096)
            self.assertGreaterEqual(count, 1)
        self.assertEqual(preview.sample_count(16), 2)

    def test_cache_variants_are_separate_and_legacy_key_is_preserved(self):
        import hashlib
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'sample';path.write_bytes(b'video')
            stat=path.stat()
            expected=hashlib.sha256(f'{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}:fill-v2'.encode()).hexdigest()
            self.assertEqual(preview.fingerprint(path), expected)
            self.assertNotEqual(expected, preview.fingerprint(path, True))

    def test_maximum_canvas_high_entropy_encoding_stays_bounded(self):
        data=random.Random(42).randbytes(4000*3600*3)
        image=preview._jpeg(4000,3600,data,lambda:None)
        self.assertTrue(image.startswith(b'\xff\xd8'))
        self.assertLessEqual(len(image),5*1024*1024)
        probe=subprocess.run(['ffprobe','-v','error','-show_entries','stream=width,height','-of','json','pipe:0'],input=image,capture_output=True,check=True)
        dimensions=json.loads(probe.stdout)['streams'][0]
        self.assertEqual((dimensions['width'],dimensions['height']),(4000,3600))

    def test_actual_jpeg_and_legacy_fill(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'wide.mp4'
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=red:s=640x240:r=12','-t','2','-c:v','libx264','-threads','1','-pix_fmt','yuv420p',str(path)],check=True)
            for detail, signature, content_type in [(False,b'\x89PNG','image/png'),(True,b'\xff\xd8','image/jpeg')]:
                sprite=preview.generate_sprite(path,detail=detail)
                self.assertTrue(sprite['data'].startswith(signature))
                self.assertEqual(sprite['content_type'],content_type)
                self.assertLessEqual(sprite['bytes'],5*1024*1024)
                result=subprocess.run(['ffmpeg','-v','error','-threads','1','-i','pipe:0','-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],input=sprite['data'],capture_output=True,check=True)
                self.assertEqual(len(result.stdout),160*90*3)
                for x,y in [(0,0),(159,0),(0,89),(159,89)]:
                    at=(y*160+x)*3;r,g,b=result.stdout[at:at+3]
                    self.assertGreater(r,200);self.assertLess(g,25);self.assertLess(b,25)

    def test_encoder_stdin_survives_cooperative_timeout_retries(self):
        data=b'x'*1_000_000
        result=preview._run_idle([sys.executable,'-c','import sys,time;time.sleep(.4);print(len(sys.stdin.buffer.read()))'],lambda:None,3,input_data=data)
        self.assertEqual(result.stdout,b'1000000\n')

    def test_dense_seek_decodes_past_long_gop_keyframe(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'changing.mp4'
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=red:s=160x90:r=12:d=4','-f','lavfi','-i','color=c=green:s=160x90:r=12:d=4','-filter_complex','[0:v][1:v]concat=n=2:v=1:a=0[v]','-map','[v]','-c:v','libx264','-threads','1','-g','240','-keyint_min','240','-sc_threshold','0','-pix_fmt','yuv420p',str(path)],check=True)
            sprite=preview.generate_sprite(path,detail=True)
            self.assertEqual(sprite['count'],2)
            result=subprocess.run(['ffmpeg','-v','error','-threads','1','-i','pipe:0','-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],input=sprite['data'],capture_output=True,check=True)
            self.assertGreater(result.stdout[0],200)
            at=160*3
            self.assertLess(result.stdout[at],25)
            self.assertGreater(result.stdout[at+1],80)

    def test_encoder_child_is_reaped_when_playback_starts(self):
        with tempfile.TemporaryDirectory() as folder:
            marker=Path(folder)/'encoding'
            children=[];original=preview.subprocess.Popen
            def capture(*args,**kwargs):
                child=original(*args,**kwargs);children.append(child);return child
            def cooperate():
                if marker.exists():raise RuntimeError('Playback active')
            command=[sys.executable,'-c','import sys,pathlib,time;sys.stdin.buffer.read();pathlib.Path(sys.argv[1]).touch();time.sleep(10)',str(marker)]
            with patch.object(preview.subprocess,'Popen',capture):
                with self.assertRaisesRegex(RuntimeError,'Playback active'):
                    preview._run_idle(command,cooperate,12,input_data=b'x'*500000)
            self.assertIsNotNone(children[0].poll())


class EndpointContract(unittest.TestCase):
    def setUp(self):
        # Load the real endpoint functions with dependency fakes, without opening databases.
        tree=ast.parse((ROOT/'api/router/files/previews.py').read_text())
        functions=[node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))]
        for node in functions:node.decorator_list=[]
        self.docs={};self.queued=[]
        class Collection:
            async def find_one(inner,query,projection):return self.docs.get(query['_id'])
            async def update_one(inner,*args):pass
        self.namespace={'Request':object,'Path':Path,'os':__import__('os'),'datetime':__import__('datetime').datetime,
            'authenticate_user':lambda request:None,'media_path':lambda path:Path('/downloads/sample.mkv'),
            'fingerprint':lambda path,detail=False:'dense' if detail else 'legacy',
            'db':types.SimpleNamespace(media_previews=Collection()),
            'redis':types.SimpleNamespace(exists=lambda key:False,set=lambda *a,**kw:True),
            'Response':lambda data,**kw:types.SimpleNamespace(data=data,**kw)}
        exec(compile(ast.Module(body=functions,type_ignores=[]),'<preview-endpoints>','exec'),self.namespace)
        self.task=types.ModuleType('tasks.media_previews')
        self.task.generate_preview=types.SimpleNamespace(delay=lambda *a,**kw:self.queued.append((a,kw)))

    def call(self,name,**kwargs):
        with patch.dict(sys.modules,{'tasks.media_previews':self.task}),patch.dict(__import__('os').environ,{'MEDIA_PREVIEWS_ENABLED':'1'}):
            return asyncio.run(self.namespace[name]('sample.mkv',None,**kwargs))

    def test_coarse_fallback_queues_dense_and_preserves_legacy_image(self):
        self.docs['legacy']={'count':100}
        result=self.call('preview',detail=True)
        self.assertEqual(result['status'],'ready');self.assertEqual(result['detail_status'],'queued')
        self.assertFalse(result['detail']);self.assertNotIn('detail=true',result['image'])
        self.assertEqual(self.queued,[ (('/downloads/sample.mkv',),{'detail':True}) ])

    def test_dense_ready_and_legacy_mime_fallback(self):
        self.docs['dense']={'count':936,'content_type':'image/jpeg','data':b'jpeg'}
        result=self.call('preview',detail=True)
        self.assertEqual(result['detail_status'],'ready');self.assertTrue(result['detail'])
        self.assertIn('&detail=true',result['image']);self.assertFalse(self.queued)
        image=self.call('preview_image',detail=True)
        self.assertEqual(image.media_type,'image/jpeg')
        self.assertEqual(image.headers,{'Cache-Control':'private, max-age=3600','ETag':'dense'})
        self.docs['legacy']={'count':100,'data':b'oldpng'}
        self.assertEqual(self.call('preview_image').media_type,'image/png')
        result=self.call('preview')
        self.assertNotIn('detail_status',result);self.assertNotIn('detail=true',result['image'])

    def test_dense_failure_retains_ready_coarse_preview(self):
        self.docs['legacy']={'count':100}
        self.namespace['redis'].exists=lambda key:True
        result=self.call('preview',detail=True)
        self.assertEqual(result['status'],'ready')
        self.assertEqual(result['detail_status'],'unavailable')
        self.assertEqual(result['count'],100)
        self.assertFalse(self.queued)

    def test_no_coarse_returns_queued_without_image(self):
        result=self.call('preview',detail=True)
        self.assertEqual(result,{'status':'queued','detail':False,'detail_status':'queued'})


if __name__=='__main__':unittest.main()
