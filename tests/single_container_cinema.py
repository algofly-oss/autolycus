"""Disposable catalog integration: own files only, grouping, variants and profile history."""
import json,shutil,subprocess
from pathlib import Path
import requests
from pymongo import MongoClient
f=json.loads(Path('/data/public-player-fixture.json').read_text());base='http://127.0.0.1';s=requests.Session();s.post(base+'/api/auth/signin',json={'username':f['username'],'password':f['password']}).raise_for_status()
h=json.loads(Path('/run/autolycus/health.json').read_text());db=MongoClient(h['mongo_uri'])[h['database']];uid=str(db.users.find_one({'username':f['username']})['_id']);root=Path('/downloads')/uid/'cinema-fixture';root.mkdir(exist_ok=True)
source=Path('/downloads/playback-fixtures/tracks.mp4')
for name in ['Night.Journey.2024.1080p.mp4','Night.Journey.2024.1080p_144p.mp4','Orbit.S01E10.1080p.mp4','Orbit.S01E02.1080p.mp4','Orbit.S01E01.1080p.mp4','Sample.mp4']:
 shutil.copyfile(source,root/name)
(root/'Orbit.S01E10.1080p.en.srt').write_text('1\n00:00:00,000 --> 00:00:35,000\nA clean, understated subtitle.\n')
(root/'.hidden').mkdir(exist_ok=True);shutil.copyfile(source,root/'.hidden/Secret.Movie.2020.mp4')
outside=Path('/downloads')/'not-this-account';outside.mkdir(exist_ok=True);shutil.copyfile(source,outside/'Private.Movie.2020.mp4')
# A symlink cannot pull another account into the catalog.
link=root/'foreign';link.unlink(missing_ok=True);link.symlink_to(outside,target_is_directory=True)
poster=Path('/data/cinema-fixture.png');subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=0x30435b:s=400x600','-frames:v','1','-threads','1',str(poster)],check=True)
path=str((root/'Night.Journey.2024.1080p.mp4').relative_to('/downloads'))
db.movie_metadata.update_one({'user_id':uid,'relative_path':path},{'$set':{'title':'Night Journey','year':2024,'overview':'A quiet journey across unfamiliar skies.','poster_bytes':poster.read_bytes(),'poster_mime':'image/png'}},upsert=True)
from redis import Redis
redis=Redis(password=json.loads(Path('/data/secrets.json').read_text())['REDIS_PASSWORD'])
redis.delete('cinema:catalog:v1:'+uid,'cinema:catalog:v2:'+uid)
s.post(base+'/api/files/playback/progress',json={'path':path,'position':12,'duration':36}).raise_for_status()
r=s.get(base+'/api/files/cinema');r.raise_for_status();data=r.json();items=data['items'];movie=next(i for i in items if i['title']=='Night Journey');series=next(i for i in items if i['title']=='Orbit')
assert len(movie['files'])==1,movie
assert [f['episode'] for f in series['files']]==[1,2,10],series
assert movie['progress']['position']==12 and movie['poster'].startswith('/api/files/media-poster/')
assert not any('Private Movie' in i['title'] or 'Secret Movie' in i['title'] or i['title'].lower()=='sample' for i in items)
assert all(f['path'].startswith(uid+'/') for i in items for f in i['files'])
other=next(p for p in s.get(base+'/api/auth/profiles').json()['profiles'] if p['name']=='Studio')
second=s.get(base+'/api/files/cinema',headers={'X-Profile-ID':other['id']}).json();assert next(i for i in second['items'] if i['title']=='Night Journey')['progress'] is None
assert requests.get(base+'/api/files/cinema').status_code>=400
first=series['files'][0]['path'];s.post(base+'/api/files/playback/progress',json={'path':first,'position':36,'duration':36,'completed':True}).raise_for_status()
updated=s.get(base+'/api/files/cinema').json();series=next(i for i in updated['items'] if i['title']=='Orbit');assert series['next_episode'] and series['resume_path']==series['files'][1]['path']
Path('/data/cinema-fixture.json').write_text(json.dumps({'movie':movie,'series':series,'username':f['username'],'password':f['password']}))
print('PASS: scoped cinema discovery, hidden/sample/symlink exclusion, movie/episode grouping, natural episode order, quality deduplication, cached posters, profile-isolated history and next-episode continuation',flush=True)
# Combined progress includes unwatched episodes and counts quality variants once.
paths=[file['path'] for file in series['files']]
for path in paths:s.post(base+'/api/files/playback/progress',json={'path':path,'position':0,'duration':100}).raise_for_status()
s.post(base+'/api/files/playback/progress',json={'path':paths[0],'position':80,'duration':100}).raise_for_status()
r=s.post(base+'/api/files/playback/progress/batch',json={'entries':[{'path':str(root.relative_to('/downloads')),'directory':True},{'path':paths[0],'directory':False}]});r.raise_for_status();records=r.json()['progress'];folder=records[str(root.relative_to('/downloads'))]
# One movie at 1/3 plus three episodes with only 0.8 episode watched.
assert folder['files_count']==4 and abs(folder['position']-(.8+1/3))<.001,folder
assert records[paths[0]]['position']==80 and records[paths[0]]['duration']==100
catalog=s.get(base+'/api/files/cinema').json();series_progress=next(i for i in catalog['items'] if i['title']=='Orbit')['watch_progress'];assert series_progress['duration']==3 and abs(series_progress['position']-.8)<.001
print('PASS: combined folder/series progress includes unwatched episodes, preserves file progress and deduplicates quality copies',flush=True)
