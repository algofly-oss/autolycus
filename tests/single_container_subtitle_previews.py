"""Disposable-container checks: subtitle/provider contracts and bounded DB previews."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import struct
import time
import requests

# Use the running disposable API's environment without printing any credentials.
pid=Path('/run/autolycus/services/api').read_text().strip()
for entry in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0'):
    if b'=' in entry:
        key,value=entry.split(b'=',1);os.environ[key.decode()]=value.decode()
import httpx

s=requests.Session();base='http://127.0.0.1/api'
for action in ('signup','signin'):
    response=s.post(base+'/auth/'+action,json={'name':'Subtitle fixture','username':'subtitle-fixture@example.test','password':'Subtitle-fixture-123!'});response.raise_for_status()
user=s.get(base+'/auth/me').json();uid=str(user.get('id') or user.get('_id') or '')
# account response varies; get the ID directly from this disposable database.
from pymongo import MongoClient
health=json.loads(Path('/run/autolycus/health.json').read_text())
client=MongoClient(health['mongo_uri']);database=client[health['database']]
uid=str(database.users.find_one({'username':'subtitle-fixture@example.test'})['_id'])
root=Path('/downloads')/uid/'subtitle-fixture';root.mkdir(parents=True,exist_ok=True)
source=root/'Show.S01E02.mp4';shutil.copyfile('/downloads/playback-fixtures/tracks.mp4',source)
relative=str(source.relative_to('/downloads'))

async def verify():
    from main import app
    from shared.modules import opensubtitles_client as provider
    original_call,original_download=provider.call,provider.download
    calls=[]
    async def fake_call(user,method,endpoint,**kwargs):
        calls.append((method,endpoint,kwargs))
        return {'data':[{'attributes':{'language':'en','release':'Fixture release','moviehash_match':True,'download_count':10,'files':[{'file_id':1234}]}}]}
    async def fake_download(user,file_id):return '1\n00:00:00,000 --> 00:00:05,000\nMatched subtitle\n'
    provider.call,provider.download=fake_call,fake_download
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://127.0.0.1',cookies=s.cookies.get_dict()) as api:
            response=await api.post('/api/files/playback/opensubtitles/search',json={'path':relative,'language':'en'});assert response.status_code==200,response.text
            assert response.json()['results'][0]['hash_match']
            assert calls[0][2]['params']['episode_number']==2
            selected={'path':relative,'subtitle':'os:1234','language':'en','name':'Fixture release'}
            response=await api.put('/api/files/playback/subtitle-selection',json=selected);assert response.status_code==200,response.text
            response=await api.get('/api/files/playback/subtitle-selection',params={'path':relative});assert response.json()['selection']['subtitle']=='os:1234'
            response=await api.get('/api/files/playback/opensubtitles/file',params={'path':relative,'file_id':1234});assert response.status_code==200 and 'Matched subtitle' in response.text
            response=await api.get('/api/files/playback/opensubtitles/file',params={'path':relative,'file_id':9999});assert response.status_code==403
            response=await api.post('/api/files/playback/opensubtitles/search',json={'path':'playback-fixtures/tracks.mp4'});assert response.status_code==403
            response=await api.patch('/api/auth/preferences',json={'video_subtitles':{'enabled':True,'language':'hi','auto_match':True}});assert response.status_code==200,response.text
            assert (await api.get('/api/auth/me')).json()['preferences']['video_subtitles']['language']=='hi'
            response=await api.put('/api/files/playback/alternate-audio',json={'path':relative,'donor':relative,'track_id':2,'delay':1.5,'rate':1.04});assert response.status_code==200,response.text
            response=await api.get('/api/files/playback/alternate-audio',params={'path':relative});assert response.json()['selection']['delay']==1.5
            response=await api.put('/api/files/playback/alternate-audio',json={'path':relative,'donor':'playback-fixtures/tracks.mp4'});assert response.status_code==403
        print('PASS: subtitle search/hash ranking, selected download authorization, server preference persistence and account-confined alternate audio',flush=True)
    finally:provider.call,provider.download=original_call,original_download
asyncio.run(verify())

before={str(path) for path in root.iterdir()}
r=s.get(base+'/files/playback/preview',params={'path':relative});r.raise_for_status()
for _ in range(120):
    data=s.get(base+'/files/playback/preview',params={'path':relative}).json()
    if data.get('status')=='ready':break
    time.sleep(.5)
else:raise AssertionError('Sprite was not generated: '+str(data))
image=s.get('http://127.0.0.1'+data['image']);image.raise_for_status()
assert image.content.startswith(b'\x89PNG\r\n\x1a\n')
assert struct.unpack('!II',image.content[16:24])==(data['columns']*160,data['rows']*90)
assert len(image.content)<=5*1024*1024
assert before=={str(path) for path in root.iterdir()}
assert database.media_previews.find_one({'duration':data['duration']}) is not None
print('PASS: real queued FFmpeg contact sheet stored in MongoDB, valid bounded PNG, no files added beside the movie',flush=True)
