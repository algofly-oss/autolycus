import ast
from pathlib import Path
import re
import tempfile
import types
import unittest

SOURCE=Path(__file__).resolve().parents[1]/'api/shared/modules/preview_cache.py'

class Cleanup(unittest.TestCase):
    def setUp(self):
        self.ns={'Path':Path,'re':re,'fingerprint':lambda path,detail=False:str(path)+':'+str(detail)}
        functions=[n for n in ast.parse(SOURCE.read_text()).body if isinstance(n,ast.FunctionDef)]
        exec(compile(ast.Module(body=functions,type_ignores=[]),str(SOURCE),'exec'),self.ns)

    def test_deleted_tree_matches_legacy_keys_and_exact_path_boundaries(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'movie[1]';target.mkdir();(target/'film.mkv').touch()
            keys=self.ns['preview_keys_for_tree'](target)
            self.assertEqual(len(keys),2)
            queries=[]
            self.ns['delete_cached_previews'](types.SimpleNamespace(delete_many=queries.append),target,keys)
            choices=queries[0]['$or']
            self.assertEqual(choices[0]['_id']['$in'],keys)
            pattern=choices[2]['source_path']['$regex']
            self.assertIsNotNone(re.search(pattern,str(target/'film.mkv')))
            self.assertIsNone(re.search(pattern,str(target)+'-other/film.mkv'))

    def test_scan_removes_missing_sources_and_keeps_existing_files(self):
        with tempfile.TemporaryDirectory() as folder:
            present=Path(folder)/'present.mkv';present.touch()
            docs=[{'_id':'keep','source_path':str(present)}, {'_id':'remove','source_path':str(Path(folder)/'gone.mkv')}]
            deleted=[]
            collection=types.SimpleNamespace(find=lambda *args:docs,delete_one=deleted.append)
            self.ns['prune_deleted_previews'](collection)
            self.assertEqual(deleted,[{'_id':'remove'}])
            self.assertTrue(present.is_file())

if __name__=='__main__':unittest.main()
