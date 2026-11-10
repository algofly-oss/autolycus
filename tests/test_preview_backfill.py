"""Backfill must skip cached work, respect boundaries, and make bounded progress."""
import ast
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).resolve().parents[1]/'api/tasks/media_previews.py'

class Redis:
    def __init__(self):self.values={}
    def get(self,key):return self.values.get(key)
    def exists(self,key):return key in self.values
    def set(self,key,value,nx=False,**kwargs):
        if nx and key in self.values:return False
        self.values[key]=value
        return True
    def delete(self,key):self.values.pop(key,None)
    def lock(self,*args,**kwargs):return types.SimpleNamespace(acquire=lambda **kw:True,release=lambda:None)

class Backfill(unittest.TestCase):
    def setUp(self):
        self.redis=Redis();self.queued=[];self.ready=set();self.docs=[]
        collection=types.SimpleNamespace(find_one=lambda query,projection:{'_id':query['_id']} if query['_id'] in self.ready else None)
        database=types.SimpleNamespace(media_previews=collection,torrents=types.SimpleNamespace(find=lambda *args:self.docs))
        class Client:
            def __getitem__(inner,key):return database
            def close(inner):pass
            def __enter__(inner):return inner
            def __exit__(inner,*args):pass
        self.ns={'os':os,'Path':Path,'redis':self.redis,'MongoClient':lambda *args:Client(),'prune_deleted_previews':lambda collection:None,
                 'fingerprint':lambda path,detail=False:str(path)+':'+str(detail),
                 'generate_preview':types.SimpleNamespace(delay=lambda *args,**kwargs:self.queued.append((args,kwargs)))}
        tree=ast.parse(SOURCE.read_text())
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('queue_missing_previews','completed_video_paths','backfill_missing_previews') or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='VIDEO_SUFFIXES' for t in n.targets)]
        for node in nodes:
            if isinstance(node,ast.FunctionDef):node.decorator_list=[]
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),self.ns)
        self.collection=collection

    def test_cached_failed_and_leased_variants_are_not_requeued(self):
        self.ready.add('movie:False')
        self.assertEqual(self.ns['queue_missing_previews']('movie',self.collection),1)
        self.assertTrue(self.queued[0][1]['detail'])
        self.assertEqual(self.ns['queue_missing_previews']('movie',self.collection),0)
        self.redis.set('preview-failed:other:False',1)
        self.redis.set('preview-failed:other:True',1)
        self.assertEqual(self.ns['queue_missing_previews']('other',self.collection),0)

    def test_dispatch_failure_releases_lease(self):
        def fail(*args,**kwargs):raise RuntimeError('broker unavailable')
        self.ns['generate_preview'].delay=fail
        with self.assertRaises(RuntimeError):self.ns['queue_missing_previews']('movie',self.collection)
        self.assertFalse(self.redis.exists('preview-job:movie:False'))

    def test_dense_generation_waits_for_first_usable_coarse_sheet(self):
        function=next(n for n in ast.parse(SOURCE.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='generate_preview')
        function.decorator_list=[];function.name='run_generate_preview'
        exec(compile(ast.Module(body=[function],type_ignores=[]),str(SOURCE),'exec'),self.ns)
        def retry(**kwargs):raise RuntimeError('retry')
        with patch.dict(os.environ,{'MONGO_DATABASE_URI':'unused','MONGO_DATABASE_NAME':'unused','MEDIA_PREVIEWS_ENABLED':'1'}):
            with self.assertRaisesRegex(RuntimeError,'retry'):
                self.ns['run_generate_preview'](types.SimpleNamespace(retry=retry),'movie',detail=True)
        self.assertEqual(self.queued,[(('movie',),{'detail':False})])

    def test_completed_only_symlink_safety_and_cursor_progress(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'DOWNLOAD_PATH': '', 'MONGO_DATABASE_URI':'unused','MONGO_DATABASE_NAME':'unused','MEDIA_PREVIEWS_ENABLED':'1'}):
            os.environ['DOWNLOAD_PATH']=directory
            root=Path(directory);finished=root/'user'/'finished';finished.mkdir(parents=True)
            for index in range(7):(finished/f'{index}.mkv').touch()
            (finished/'outside.mkv').symlink_to('/etc/hosts')
            (finished/'hidden').symlink_to('/tmp',target_is_directory=True)
            incomplete=root/'user'/'incomplete';incomplete.mkdir();(incomplete/'partial.mkv').touch()
            self.docs=[{'user_id':'user','info_hash':'finished'}]
            first=self.ns['backfill_missing_previews']()
            self.assertEqual(first,{'queued':8,'checked':4})
            second=self.ns['backfill_missing_previews']()
            self.assertEqual(second,{'queued':6,'checked':3})
            self.assertEqual(len(self.queued),14)
            self.assertFalse(self.redis.exists('media-preview:scan-cursor'))
            self.assertFalse(any('partial' in args[0] or 'outside' in args[0] for args,kwargs in self.queued))
            self.assertEqual(self.ns['backfill_missing_previews']()['queued'],0)

    def test_disabled_scan_does_no_work(self):
        with patch.dict(os.environ,{'MEDIA_PREVIEWS_ENABLED':'0'}):
            self.assertIsNone(self.ns['backfill_missing_previews']())
        self.assertFalse(self.queued)

if __name__=='__main__':unittest.main()
