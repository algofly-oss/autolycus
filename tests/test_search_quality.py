"""Search coverage and bounded, local Jackett metadata resolution."""
import asyncio
import hashlib
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'api'))
import httpx
import libtorrent as lt
from shared.modules.search_quality import query_variants, relevance
from shared.modules.search_magnets import canonical_hash, normalize_magnet, local_download_path, fetch_magnet, attach_resolution
from shared.modules.jackett import AsyncJackett
HASH = '1234567890abcdef1234567890abcdef12345678'
BASE = 'http://jackett:9117'


class SearchTests(unittest.IsolatedAsyncioTestCase):
    def test_query_and_relevance(self):
        self.assertEqual(query_variants('Ubuntu.24.04 1080p'), ['Ubuntu.24.04 1080p', 'Ubuntu 24 04'])
        self.assertEqual(query_variants('"Exact Title" 2020'), ['"Exact Title" 2020'])
        self.assertEqual(query_variants('C++'), ['C++'])
        self.assertGreater(relevance('cafe society', 'Café.Society.1080p'), relevance('cafe society', 'Other.Title'))

    def test_local_paths_and_hashes(self):
        self.assertEqual(canonical_hash('A' * 32), '0' * 40)
        self.assertIsNone(canonical_hash('invalid'))
        self.assertEqual(normalize_magnet('magnet:?xt=urn:btih:' + HASH.upper()), 'magnet:?xt=urn:btih:' + HASH)
        self.assertEqual(local_download_path(BASE + '/dl/source/?path=signed&jackett_apikey=secret', BASE, 'source'), '/dl/source/?path=signed')
        for link in ('http://evil/dl/source/', BASE + '/api/delete', BASE + '/dl/other/', 'file:///dl/source/', 'http://user@jackett:9117/dl/source/'):
            self.assertIsNone(local_download_path(link, BASE, 'source'))

    async def test_magnet_redirect_and_query_preserved(self):
        def respond(request):
            self.assertEqual(request.url.params['path'], 'signed')
            self.assertEqual(request.url.params['jackett_apikey'], 'secret')
            return httpx.Response(302, headers={'location': 'magnet:?xt=urn:btih:' + HASH})
        result = await fetch_magnet(BASE, 'secret', '/dl/source/?path=signed', 'source', httpx.MockTransport(respond))
        self.assertIn(HASH, result)

    async def test_torrent_metadata_to_magnet(self):
        info = {b'name': b'fixture.txt', b'length': 5, b'piece length': 16384, b'pieces': hashlib.sha1(b'hello').digest()}
        expected = hashlib.sha1(lt.bencode(info)).hexdigest()
        transport = httpx.MockTransport(lambda _: httpx.Response(200, content=lt.bencode({b'info': info})))
        self.assertIn(expected, await fetch_magnet(BASE, 'key', '/dl/source/', 'source', transport))

    async def test_external_redirect_rejected(self):
        transport = httpx.MockTransport(lambda _: httpx.Response(302, headers={'location': 'https://external/file.torrent'}))
        with self.assertRaises(ValueError):
            await fetch_magnet(BASE, 'key', '/dl/source/', 'source', transport)

    async def test_oversized_response_rejected(self):
        transport = httpx.MockTransport(lambda _: httpx.Response(200, content=b'x' * (4 * 1024 * 1024 + 1)))
        with self.assertRaises(ValueError):
            await fetch_magnet(BASE, 'key', '/dl/source/', 'source', transport)

    def test_opaque_resolution_token(self):
        redis = Mock()
        item = {'TrackerId': 'source', 'Link': BASE + '/dl/source/?path=signed&jackett_apikey=secret'}
        with patch.dict(sys.modules, {'shared.factory': SimpleNamespace(redis=redis)}):
            attach_resolution(item, BASE, 'user')
        self.assertIsNone(item['Link'])
        self.assertIn('ResolveToken', item)
        self.assertNotIn('secret', str(redis.set.call_args))

    async def test_zero_and_unknown_seeds_retained(self):
        client = AsyncJackett('key')
        rows = [{'Title': 'Ubuntu', 'Seeders': 0}, {'Title': 'Ubuntu unknown'}]
        client._search_index = AsyncMock(return_value=('source', rows, None))
        result = [item async for item in client.search('Ubuntu', indexes=['source'])]
        self.assertEqual(len(result), 2)
        self.assertTrue(all(item['SearchRelevance'] == 1 for item in result))

    async def test_broader_retry_only_deep_without_results(self):
        client = AsyncJackett('key')
        calls = []
        async def round_(query, indexes, event, deep):
            calls.append(query)
            if query == 'Ubuntu':
                yield {'Title': 'Ubuntu'}
        client._search_round = round_
        result = [item async for item in client.search('Ubuntu 1080p', indexes=['source'], deep=True)]
        self.assertEqual(calls, ['Ubuntu 1080p', 'Ubuntu'])
        self.assertEqual(result[0]['__type'], 'search_status')
        calls.clear()
        self.assertEqual([item async for item in client.search('Ubuntu 1080p', indexes=['source'])], [])
        self.assertEqual(calls, ['Ubuntu 1080p'])

    async def test_no_retry_when_results_found(self):
        client = AsyncJackett('key')
        client._search_index = AsyncMock(return_value=('source', [{'Title': 'Ubuntu 1080p'}], None))
        result = [item async for item in client.search('Ubuntu 1080p', indexes=['source'], deep=True)]
        self.assertEqual(len(result), 1)
        self.assertEqual(client._search_index.await_count, 1)

    async def test_waiting_search_has_no_read_deadline_and_cancels_workers(self):
        client = AsyncJackett('key')
        self.assertIsNone(client.timeout.read)
        self.assertEqual(client.timeout.connect, 5)
        started, stopped = asyncio.Event(), asyncio.Event()
        async def slow_source(*args):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()
        client._search_index = slow_source
        iterator = client.search('Ubuntu', indexes=['source'])
        pending = asyncio.create_task(iterator.__anext__())
        await asyncio.wait_for(started.wait(), 2)
        self.assertFalse(pending.done())
        pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)
        await asyncio.wait_for(stopped.wait(), 2)
        await iterator.aclose()
