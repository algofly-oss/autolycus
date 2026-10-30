import asyncio
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'api'))
from shared.modules import search_posters as posters
import importlib.util
spec = importlib.util.spec_from_file_location('preferences_utils', Path(__file__).resolve().parents[1] / 'api/router/auth/preferences_utils.py')
preferences = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preferences)
serialize_preferences = preferences.serialize_preferences


class PosterTests(unittest.IsolatedAsyncioTestCase):
    def test_release_identity_deduplicates_quality_but_keeps_year_and_type(self):
        key, parsed, _ = posters.media_identity('The.Matrix.1999.1080p.BluRay.x264')
        self.assertEqual(key, posters.media_identity('The.Matrix.1999.720p.WEB-DL')[0])
        self.assertNotEqual(key, posters.media_identity('The.Matrix.2021.1080p')[0])
        self.assertNotEqual(key, posters.media_identity('The.Matrix.1999.1080p','tv')[0])
        self.assertEqual(posters.media_identity('Dune.2024')[1]['year'], 2024)
        self.assertEqual(posters.media_identity('Breaking.Bad.S01E02.1080p')[2], 'tv')

    def test_wrong_titles_years_oversize_and_active_mime_rejected(self):
        parsed={'title':'Dune','year':2024}
        metadata={'title':'Dune Part Two','year':2024,'poster_bytes':b'png','poster_mime':'image/png'}
        self.assertTrue(posters.acceptable_match(parsed,metadata))
        self.assertFalse(posters.acceptable_match(parsed,dict(metadata,year=2021)))
        self.assertFalse(posters.acceptable_match(parsed,dict(metadata,title='Another Film')))
        self.assertFalse(posters.acceptable_match(parsed,dict(metadata,poster_bytes=b'x'*(posters.MAX_POSTER_BYTES+1))))
        self.assertFalse(posters.acceptable_match(parsed,dict(metadata,poster_mime='text/html')))

    def test_provider_failure_uses_existing_fallback(self):
        value={'title':'Dune','year':2024,'poster_bytes':b'png'}
        with patch.object(posters,'_tmdb_search_metadata',side_effect=RuntimeError()), patch.object(posters,'_imdb_search_metadata',return_value=value) as fallback:
            self.assertEqual(posters.lookup_metadata({'title':'Dune','year':2024}),value)
            fallback.assert_called_once()

    def test_account_preference_serialization_preserves_independent_modes(self):
        self.assertEqual(serialize_preferences({'home_view_mode':'grid','search_view_mode':'list'})['search_view_mode'],'list')
        self.assertNotIn('search_view_mode',serialize_preferences({'search_view_mode':'invalid'}))
        self.assertNotIn('search_view_mode',serialize_preferences({}))

    def test_imdb_uses_bounded_thumbnail_and_rejects_foreign_images(self):
        suggestion={'l':'Dune','y':2024,'id':'tt1234567','i':{'imageUrl':'https://m.media-amazon.com/images/M/poster._V1_.jpg'}}
        response=Mock()
        response.__enter__=Mock(return_value=response)
        response.__exit__=Mock(return_value=False)
        response.iter_content.return_value=[b'image']
        response.headers={'content-type':'image/jpeg'}
        with patch.object(posters,'_search_imdb_suggestion',return_value=suggestion),patch.object(posters.requests,'get',return_value=response) as get:
            value=posters._imdb_search_metadata({'title':'Dune','year':2024})
            self.assertEqual(value['poster_bytes'],b'image')
            self.assertIn('._V1_SX360_.jpg',get.call_args.args[0])
            self.assertTrue(get.call_args.kwargs['stream'])
        suggestion['i']['imageUrl']='http://127.0.0.1/private'
        with patch.object(posters,'_search_imdb_suggestion',return_value=suggestion),patch.object(posters.requests,'get') as get:
            self.assertEqual(posters._imdb_search_metadata({'title':'Dune'}),{})
            get.assert_not_called()

    async def test_shared_lookup_survives_one_scroller_cancelling(self):
        key, _, _ = posters.media_identity('Dune.2024')
        entered, release = asyncio.Event(), asyncio.Event()
        async def work(*args):
            entered.set(); await release.wait()
            return {'id':key,'poster_url':'/poster'}
        collection=type('Collection',(),{'find_one':AsyncMock(return_value=None)})()
        with patch.object(posters,'_ensure_indexes',new=AsyncMock()),patch.object(posters,'_lookup_and_cache',side_effect=work) as lookup,patch.object(posters,'_pending',{}):
            first=asyncio.create_task(posters.search_poster(collection,'Dune.2024'))
            await entered.wait()
            second=asyncio.create_task(posters.search_poster(collection,'Dune.2024'))
            await asyncio.sleep(0)
            first.cancel(); await asyncio.gather(first,return_exceptions=True)
            release.set()
            self.assertEqual((await second)['id'],key)
            self.assertEqual(lookup.call_count,1)

    async def test_cached_lookup_skips_provider(self):
        doc={'_id':'a'*64,'title':'Dune','has_poster':True}
        collection=type('Collection',(),{'find_one':AsyncMock(return_value=doc),'update_one':AsyncMock()})()
        with patch.object(posters,'_ensure_indexes',new=AsyncMock()),patch.object(posters,'_lookup_and_cache') as lookup:
            value=await posters.search_poster(collection,'Dune.2024')
            self.assertTrue(value['poster_url'].endswith('a'*64))
            lookup.assert_not_called()

    def test_aka_release_names_share_film_cache_key(self):
        key=posters.media_identity('RRR.2022.1080p')[0]
        self.assertEqual(key,posters.media_identity('RRR.A.K.A.Rise.Roar.Revolt.2022.1080p')[0])
        self.assertEqual(key,posters.media_identity('r.r.r.2022.1080p')[0])

    def test_provider_verified_aliases_and_release_years(self):
        metadata={'title':'Monkey in a Cage','original_title':'Bandar','aliases':['Bandar'], 'year':2025,'release_years':[2025,2026],'poster_bytes':b'image'}
        self.assertTrue(posters.acceptable_match({'title':'Bandar','year':2026},metadata))
        self.assertFalse(posters.acceptable_match({'title':'Bandar','year':2024},metadata))
        self.assertFalse(posters.acceptable_match({'title':'Different Movie','year':2026},metadata))
        self.assertTrue(posters.acceptable_match({'title':'Satluj','year':2026},{'title':"Punjab '95",'original_title':'Satluj','year':2026,'poster_bytes':b'image'}))
        self.assertTrue(posters.acceptable_match({'title':'Ghamsaan','year':2026},{'title':'Ghamasaan','year':2024,'release_years':[2024,2026],'poster_bytes':b'image'}))

    def test_byte_budget_eviction_prefers_recent_and_removes_expired(self):
        now=datetime.utcnow()
        entries=[{'_id':str(i),'has_poster':True,'poster_size':20,'last_accessed':now-timedelta(minutes=i),'expires_at':now+timedelta(days=1)} for i in range(4)]
        self.assertEqual(posters.eviction_keys(entries,now,max_bytes=45),['2','3'])
        entries[0]['expires_at']=now-timedelta(seconds=1)
        self.assertEqual(set(posters.eviction_keys(entries,now,max_bytes=45)),{'0','3'})
        self.assertEqual(posters.eviction_keys(entries[1:],now,max_bytes=1000,max_entries=1),['2','3'])

    def test_negative_cache_has_smaller_entry_limit(self):
        now=datetime.utcnow()
        entries=[{'_id':str(i),'has_poster':False,'poster_size':0,'last_accessed':now-timedelta(seconds=i),'expires_at':now+timedelta(minutes=5)} for i in range(140)]
        self.assertEqual(len(posters.eviction_keys(entries,now)),12)

    def test_old_failed_lookups_are_retried_after_upgrade(self):
        query=posters.cached_query('key')
        self.assertIn({'lookup_version':2},query['$or'])

    def test_bilingual_names_use_searchable_title_without_changing_year(self):
        self.assertEqual(posters.media_identity('Патхан / Pathaan.2023.1080p')[0],posters.media_identity('Pathaan.2023.1080p')[0])
        self.assertEqual(posters.media_identity('罗摩衍那 Ramayana.2025.1080p')[0],posters.media_identity('Ramayana.2025.1080p')[0])

    def test_catalog_dotted_acronyms_match_release_acronyms(self):
        self.assertTrue(posters.matches_identity({'title':'KGF - Chapter 2','year':2022},{'title':'K.G.F: Chapter 2','year':2022}))
