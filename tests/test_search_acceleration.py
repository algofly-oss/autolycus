"""Cached streams, refresh boundaries, resource bounds and source prioritization."""
import asyncio
import json
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'api'))
from shared.modules.jackett import AsyncJackett
from shared.modules.search_acceleration import SearchAcceleration, result_key, CACHE_SECONDS, MAX_CACHE_BYTES


class Store:
    def __init__(self):
        self.values, self.hashes, self.order = {}, {}, {}
    def get(self, key): return self.values.get(key)
    def hgetall(self, key): return self.hashes.get(key, {}).copy()
    def hset(self, key, field, value): self.hashes.setdefault(key, {})[field] = value
    def eval(self, script, count, key, lru, payload, ttl, now, limit):
        self.values[key] = payload
        self.order[key] = now
        for old in sorted(self.order, key=self.order.get)[:-limit]:
            self.order.pop(old); self.values.pop(old, None)


class AccelerationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.store = Store()
        self.client = AsyncJackett('key', store=self.store)

    async def search(self, query='Ubuntu'):
        return [item async for item in self.client.search(query, indexes=['source'])]

    async def test_repeat_streams_cache_before_contacting_source(self):
        self.client._search_index = AsyncMock(return_value=('source', [{'Title':'Ubuntu', 'Seeders':5}], None))
        await self.search()
        self.client._search_index.reset_mock()
        iterator = self.client.search('Ubuntu', indexes=['source'])
        self.assertEqual((await iterator.__anext__())['__type'], 'cache_status')
        row = await iterator.__anext__()
        self.assertTrue(row['SearchCached'])
        self.assertEqual(row['Seeders'], 5)
        self.client._search_index.assert_not_awaited()
        await iterator.aclose()

    async def test_refresh_replaces_cached_source_and_empty_source(self):
        self.client._search_index = AsyncMock(return_value=('source', [{'Title':'Ubuntu', 'Seeders':5}], None))
        first = await self.search()
        self.client._search_index.return_value = ('source', [{'Title':'Ubuntu', 'Seeders':50}], None)
        second = await self.search()
        rows = [x for x in second if not x.get('__type')]
        self.assertEqual([x['Seeders'] for x in rows], [5,50])
        self.assertEqual(rows[0]['SearchResultKey'], rows[1]['SearchResultKey'])
        self.assertEqual(second[-1]['__type'], 'source_complete')
        self.client._search_index.return_value = ('source', [], None)
        await self.search()
        key = self.client.acceleration.cache_key(self.client.base_url,'Ubuntu',['source'],False)
        snapshot = await self.client.acceleration.read(key)
        self.assertEqual(snapshot['source']['rows'], [])

    async def test_errors_preserve_recent_cache_without_renewing_its_age(self):
        self.client._search_index = AsyncMock(return_value=('source', [{'Title':'Ubuntu'}], None))
        await self.search()
        key = self.client.acceleration.cache_key(self.client.base_url,'Ubuntu',['source'],False)
        before = self.store.get(key)
        self.client._search_index.return_value = ('source', [], 'failed')
        await self.search()
        self.assertEqual(self.store.get(key), before)

    async def test_source_history_orders_fast_reliable_then_unknown_then_slow(self):
        a = self.client.acceleration
        await a.observe('fast',0.1,True)
        await a.observe('slow',30,True)
        await a.observe('failure',2,False)
        self.assertEqual(a.order(['slow','new','failure','fast']),['fast','new','failure','slow'])
        restored = SearchAcceleration(self.store)
        await restored.load_metrics()
        self.assertEqual(restored.order(['slow','fast']),['fast','slow'])

    async def test_cache_scope_expiry_and_capacity(self):
        a = self.client.acceleration
        key = a.cache_key('base',' Dune  2024 ',['a','b'],False)
        self.assertEqual(key,a.cache_key('base','dune 2024',['b','a'],False))
        self.assertNotEqual(key,a.cache_key('base','dune 2021',['a','b'],False))
        self.assertNotEqual(key,a.cache_key('base','Dune 2024',['a'],False))
        self.store.values[key] = json.dumps({'old':{'time':time.time()-CACHE_SECONDS-1,'rows':[]}})
        self.assertEqual(await a.read(key),{})
        for i in range(20):
            await a.write(str(i),{'a':{'time':time.time(),'rows':[{'Title':'x'}]}})
        self.assertLessEqual(len(self.store.order),16)
        await a.write('large',{'a':{'time':time.time(),'rows':[{'Title':'x'*(MAX_CACHE_BYTES+1)}]}})
        self.assertLessEqual(len(self.store.values['large'].encode()),MAX_CACHE_BYTES)

    async def test_cancel_closes_all_workers_and_caches_completed_sources(self):
        started, stopped = asyncio.Event(), asyncio.Event()
        async def source(client, query, index, event):
            if index == 'fast':
                await started.wait()
                return index, [{'Title':'Ubuntu'}], None
            started.set()
            try: await asyncio.Event().wait()
            finally: stopped.set()
        self.client._search_index = source
        iterator = self.client.search('Ubuntu',indexes=['fast','slow'])
        self.assertEqual((await iterator.__anext__())['Title'],'Ubuntu')
        self.assertEqual((await iterator.__anext__())['__type'],'source_complete')
        await iterator.aclose()
        await asyncio.wait_for(stopped.wait(),2)
        key = self.client.acceleration.cache_key(self.client.base_url,'Ubuntu',['fast','slow'],False)
        self.assertTrue((await self.client.acceleration.read(key))['fast']['rows'])

    async def test_cache_failure_does_not_break_live_results(self):
        self.store.get = lambda _: (_ for _ in ()).throw(ConnectionError())
        self.client._search_index = AsyncMock(return_value=('source',[{'Title':'Ubuntu'}],None))
        result = await self.search()
        self.assertTrue(any(item.get('Title')=='Ubuntu' for item in result))

    def test_result_identity_keeps_sources_separate_and_ignores_seed_changes(self):
        self.assertEqual(result_key({'Title':'Ubuntu','Seeders':1},'a'),result_key({'Title':'Ubuntu','Seeders':9},'a'))
        self.assertNotEqual(result_key({'Title':'Ubuntu'},'a'),result_key({'Title':'Ubuntu'},'b'))
