"""Authenticated poster API and independent account preferences; disposable stack."""
import base64
import json
from datetime import datetime, timedelta
from pathlib import Path
import requests
from pymongo import MongoClient
from shared.modules.search_posters import media_identity

base='http://127.0.0.1'
session=requests.Session()
response=session.post(base+'/api/auth/signin',json={'username':'single-container-smoke@example.test','password':'Smoke-Test-Password-123!'},timeout=10)
response.raise_for_status()

def preferences(**payload):
    response=session.patch(base+'/api/auth/preferences',json=payload,timeout=10)
    response.raise_for_status()
    return response.json()['preferences']

value=preferences(home_view_mode='grid',search_view_mode='grid')
assert value['search_view_mode']=='grid' and value['home_view_mode']=='grid'
assert session.get(base+'/api/auth/me',timeout=10).json()['preferences']['search_view_mode']=='grid'
value=preferences(search_view_mode='list')
assert value['home_view_mode']=='grid' and value['search_view_mode']=='list'
assert session.patch(base+'/api/auth/preferences',json={'search_view_mode':'invalid'},timeout=10).status_code==400
assert requests.patch(base+'/api/auth/preferences',json={'search_view_mode':'grid'},timeout=10).status_code in (400,401,403)

# Stable local PNG fixture keeps the integration tests independent of provider uptime.
png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jS1sAAAAASUVORK5CYII=')
key,_,_=media_identity('Dune.2024.1080p.WEB-DL')
health=json.loads(Path('/run/autolycus/health.json').read_text())
with MongoClient(health['mongo_uri']) as client:
    collection=client[health['database']].search_media_metadata
    collection.replace_one({'_id':key},{'_id':key,'title':'Dune: Part Two','year':2024,'media_type':'movie','has_poster':True,'poster_mime':'image/png','poster_bytes':png,'vote_average':8.2,'imdb_url':'https://www.imdb.com/title/tt15239678/','updated_at':datetime.utcnow(),'expires_at':datetime.utcnow()+timedelta(days=1)},upsert=True)
response=session.post(base+'/api/torrent/search-poster',json={'name':'Dune.2024.2160p.BluRay'},timeout=10)
response.raise_for_status();metadata=response.json()
assert metadata['title']=='Dune: Part Two' and metadata['id']==key
response=session.get(base+metadata['poster_url'],timeout=10)
assert response.content==png and response.headers['content-type']=='image/png'
assert 'private' in response.headers['cache-control']
assert requests.get(base+metadata['poster_url'],timeout=10).status_code in (400,401,403)
assert requests.post(base+'/api/torrent/search-poster',json={'name':'Dune'},timeout=10).status_code in (400,401,403)
assert session.post(base+'/api/torrent/search-poster',json={'name':'','kind':'movie'},timeout=10).status_code==422
assert session.get(base+'/api/torrent/search-poster/invalid',timeout=10).status_code==404

# Exercise the budget against actual Mongo documents, using a small test budget.
import asyncio
from unittest.mock import patch
from motor.motor_asyncio import AsyncIOMotorClient
from shared.modules import search_posters as policy

async def verify_policy():
    client=AsyncIOMotorClient(health['mongo_uri'])
    collection=client[health['database']].search_media_metadata_policy_test
    try:
        await collection.delete_many({})
        now=datetime.utcnow()
        await collection.insert_many([{'_id':str(i),'has_poster':True,'poster_size':200,'last_accessed':now-timedelta(minutes=i),'expires_at':now+timedelta(days=1)} for i in range(4)])
        original=policy.eviction_keys
        with patch.object(policy,'eviction_keys',side_effect=lambda rows:original(rows,max_bytes=450)):
            await policy.prune_cache(collection)
        assert {row['_id'] async for row in collection.find({})}=={'0','1'}
        await collection.delete_many({})
        policy._slots=asyncio.Semaphore(3)
        policy._cache_lock=asyncio.Lock()
        policy._index_lock=asyncio.Lock()
        policy._indexes_ready=False
        with patch.object(policy,'lookup_metadata',return_value={}):
            await policy.search_poster(collection,'NoMatch.2026')
        row=await collection.find_one({})
        assert row['lookup_version']==2 and not row['has_poster']
        assert 0<(row['expires_at']-datetime.utcnow()).total_seconds()<=300
        # Old failed entries must not prevent retries after the matching upgrade.
        await collection.update_one({'_id':row['_id']},{'$unset':{'lookup_version':''}})
        with patch.object(policy,'lookup_metadata',return_value={}) as lookup:
            await policy.search_poster(collection,'NoMatch.2026')
            assert lookup.call_count==1
        print('PASS: real Mongo byte-budget eviction, short negative-cache TTL and old-failure retry')
    finally:
        await collection.drop()
        client.close()

asyncio.run(verify_policy())
Path('/data/search-poster-fixture.json').write_text(json.dumps(metadata))
print('PASS: independent server preferences, invalid/auth checks, cached release deduplication and authenticated same-origin poster delivery')
