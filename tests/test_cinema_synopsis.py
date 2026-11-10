"""Incomplete catalog details should use the matched IMDb plot and retry sooner."""
import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'api'))
from shared.modules import cinema_discovery as cinema
from shared.modules import search_posters


class SynopsisTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_description_uses_imdb_plot(self):
        meta={'id':'tt1234567','name':'Example'}
        with patch.object(cinema,'redis',Mock(get=Mock(return_value=None))), patch.object(cinema,'SLOTS',asyncio.Semaphore(2)), patch.object(cinema,'fetch_json',return_value={'meta':meta}), patch.object(cinema,'store') as store, patch.object(search_posters,'_imdb_title_details',return_value={'overview':'Verified synopsis'}) as fallback:
            result=await cinema.title_details('tt1234567','movie')
            self.assertEqual(result['overview'],'Verified synopsis')
            self.assertEqual(fallback.call_args.args[0],'tt1234567')
            self.assertEqual(store.call_args.args[2],7*86400)

    async def test_existing_description_is_preserved(self):
        meta={'id':'tt1234567','name':'Example','description':'Catalog synopsis'}
        with patch.object(cinema,'redis',Mock(get=Mock(return_value=None))), patch.object(cinema,'SLOTS',asyncio.Semaphore(2)), patch.object(cinema,'fetch_json',return_value={'meta':meta}), patch.object(cinema,'store'), patch.object(search_posters,'_imdb_title_details') as fallback:
            result=await cinema.title_details('tt1234567','movie')
            self.assertEqual(result['overview'],'Catalog synopsis')
            fallback.assert_not_called()

    async def test_incomplete_description_has_short_cache_lifetime(self):
        meta={'id':'tt1234567','name':'Example'}
        with patch.object(cinema,'redis',Mock(get=Mock(return_value=None))), patch.object(cinema,'SLOTS',asyncio.Semaphore(2)), patch.object(cinema,'fetch_json',return_value={'meta':meta}), patch.object(cinema,'store') as store, patch.object(search_posters,'_imdb_title_details',return_value={}):
            result=await cinema.title_details('tt1234567','movie')
            self.assertEqual(result['overview'],'')
            self.assertEqual(store.call_args.args[2],900)


if __name__=='__main__':
    unittest.main()
