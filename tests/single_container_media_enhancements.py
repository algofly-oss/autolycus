"""Disposable container only: media names, quality, bookmarks, jobs and public links."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import requests
from pymongo import MongoClient
from redis import Redis

BASE='http://127.0.0.1';USER='enhanced-media@example.test';PASSWORD='Enhanced-media-123!'
s=requests.Session()
for action in ('signup','signin'):
    r=s.post(BASE+'/api/auth/'+action,json={'name':'Enhanced media','username':USER,'password':PASSWORD});r.raise_for_status()
def api(method,path,**kwargs):
    r=s.request(method,BASE+'/api'+path,timeout=30,**kwargs);r.raise_for_status();return r.json()
def until(predicate):
    for _ in range(150):
        if predicate():return
        time.sleep(.2)
    raise AssertionError('Media fixture timed out')
health=json.loads(Path('/run/autolycus/health.json').read_text())
client=MongoClient(health['mongo_uri']);db=client[health['database']]
secrets=json.loads(Path('/data/secrets.json').read_text());cache=Redis(host='127.0.0.1',password=secrets['REDIS_PASSWORD'])
user=db.users.find_one({'username':USER});uid=str(user['_id']);info_hash=hashlib.sha1(b'media-fixture').hexdigest()
root=Path('/downloads')/uid/info_hash;root.mkdir(parents=True,exist_ok=True)
for child in root.iterdir():
    if child.is_file():
        cache.delete(f'transcoding_progress/{child}',f'transcoding_progress/{child}/kill')
        child.unlink()
db.public_urls.delete_many({'user_id':uid,'info_hash':info_hash})
source=root/'Show.S01E02.The.Pilot.1080p.mp4'
subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=320x180:rate=24','-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','3','-c:v','libx264','-threads','1','-preset','ultrafast','-c:a','aac',str(source)],check=True)
db.torrents.update_one({'info_hash':info_hash,'user_id':user['_id']},{'$set':{'name':'Show.S01E01-E10.Complete.1080p','save_dir':str(root)}},upsert=True)
rel=str(source.relative_to('/downloads'))
rows=api('GET','/files/browse',params={'path':str(root.relative_to('/downloads')),'names_only':'true'})
row=next(row for row in rows if row['name']==source.name)
assert row['display_name']=='Show · S01 E02 · The Pilot',row
assert row['episode_info']['episode']==2
public=api('POST','/files/generate-public-url',json={'path':str(source)})
assert 'S01.E02' in public['key'] and 'E01-' not in public['key'],public
assert requests.get(BASE+'/api/files/public/'+public['key']).content==source.read_bytes()
record=db.public_urls.find_one({'path':str(source)});old_title='Legacy-readable-link-'+record['path_hash']+'.mp4'
db.public_urls.update_one({'_id':record['_id']},{'$set':{'title':old_title}})
assert api('POST','/files/generate-public-url',json={'path':str(source)})['key']==old_title
assert requests.get(BASE+'/api/files/public/'+old_title).status_code==200
print('PASS: readable shared PTN labels, file episode wins over pack, public link bytes and legacy URL preservation',flush=True)

assert api('GET','/auth/me')['preferences']['video_quality']=='auto'
assert api('PATCH','/auth/preferences',json={'video_quality':'720p'})['preferences']['video_quality']=='720p'
assert api('GET','/auth/me')['preferences']['video_quality']=='720p'
assert s.patch(BASE+'/api/auth/preferences',json={'video_quality':'unlimited'}).status_code==400
api('PATCH','/auth/preferences',json={'video_quality':'auto'})
for height in [144,720]:shutil.copyfile(source,source.with_name(source.stem+f'_{height}p.mp4'))
unfinished=source.with_name(source.stem+'_480p.mp4');shutil.copyfile(source,unfinished)
cache.set(f'transcoding_progress/{unfinished}',json.dumps({'progress':10}))
versions=api('GET','/files/playback/info',params={'path':rel})['versions']
assert [item['quality'] for item in versions]==['original','144p','720p'],versions
cache.delete(f'transcoding_progress/{unfinished}');unfinished.unlink()
variant=source.with_name(source.stem+'_720p.mp4')
assert api('GET','/files/playback/info',params={'path':str(variant.relative_to('/downloads'))})['versions'][0]['path']==rel
print('PASS: account-synced Auto/manual preference and completed existing quality files; in-progress files excluded',flush=True)

progress=api('POST','/files/playback/progress',json={'path':rel,'position':1.2,'duration':3})
assert progress['position']==1.2
assert api('GET','/files/playback/progress',params={'path':rel})['progress']['position']==1.2
batch=api('POST','/files/playback/progress/batch',json={'entries':[{'path':rel},{'path':str(root.relative_to('/downloads')),'directory':True}]})['progress']
assert len(batch)==2 and all(value['position']==1.2 for value in batch.values())
assert requests.get(BASE+'/api/files/playback/progress',params={'path':rel}).status_code>=400
assert s.post(BASE+'/api/files/playback/progress',json={'path':'../etc/passwd','position':1,'duration':3}).status_code==403
print('PASS: authenticated per-account playback bookmarks and file/folder card progress',flush=True)

profiles=api('GET','/auth/profiles')['profiles']
assert profiles[0]['id']=='default'
created=api('POST','/auth/profiles',json={'name':'Other viewer','avatar':'film'})['profile']
headers={'X-Profile-ID':created['id']}
assert api('GET','/files/playback/progress',params={'path':rel},headers=headers)['progress'] is None
api('POST','/files/playback/progress',json={'path':rel,'position':2.1,'duration':3},headers=headers)
assert api('GET','/files/playback/progress',params={'path':rel},headers=headers)['progress']['position']==2.1
assert api('GET','/files/playback/progress',params={'path':rel})['progress']['position']==1.2
assert api('PATCH','/auth/preferences',json={'video_quality':'720p'},headers=headers)['preferences']['video_quality']=='720p'
assert api('GET','/auth/me')['preferences']['video_quality']=='auto'
updated=api('PATCH','/auth/profiles/'+created['id'],json={'name':'Renamed viewer','avatar':'star'})['profile']
assert updated['name']=='Renamed viewer' and updated['avatar']=='star'
assert s.get(BASE+'/api/files/playback/progress',params={'path':rel},headers={'X-Profile-ID':'not-owned'}).status_code==404
print('PASS: server-stored aliases/avatars, independent per-profile history and quality, legacy/default bookmarks preserved, foreign profile rejected',flush=True)

# CPU and NVENC use the same output contract. Exercise both native encoders.
import sys
sys.path.insert(0,'/app')
from shared.modules.transcode_backend import encoding_command,probe,gpu_ready
metadata=probe(str(source));cpu=root/'cpu-check.mp4'
subprocess.run(encoding_command(str(source),str(cpu),'144p',metadata['streams'],False),check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
assert probe(str(cpu))['streams'][0]['codec_name']=='h264'
if os.environ.get('TRANSCODE_USE_GPU')=='1':
    assert gpu_ready()
    gpu=root/'gpu-check.mp4'
    subprocess.run(encoding_command(str(source),str(gpu),'144p',metadata['streams'],True),check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    assert probe(str(gpu))['streams'][0]['codec_name']=='h264'
assert shutil.which('HandBrakeCLI') is None
print('PASS: real bounded-thread FFmpeg CPU and optional NVIDIA encode; HandBrake removed',flush=True)

# Hold both application slots: all selected jobs must queue and be cancellable.
locks=[cache.lock(f'transcode:slot:{i}',timeout=60) for i in range(2)]
for lock in locks:assert lock.acquire(blocking=False)
try:
    selected=[]
    for number in [1,2,3]:
        path=root/f'bulk-{number}.mp4';shutil.copyfile(source,path);selected.append(str(path))
    result=api('POST','/files/transcode/bulk',json={'paths':selected,'action':'start','resolution':'240p'})
    assert len(result['results'])==3 and all(row['ok'] for row in result['results']),result
    time.sleep(1)
    cancelled=api('POST','/files/transcode/bulk',json={'paths':selected,'action':'cancel'})
    assert len(cancelled['results'])==3 and all(row['ok'] for row in cancelled['results']),cancelled
    assert not any(Path(path[:-4]+'_240p.mp4').exists() for path in selected)
finally:
    for lock in locks:lock.release()
job=api('POST','/files/transcode/start',params={'path':str(source),'resolution':'240p'})
output=source.with_name(source.stem+'_240p.mp4')
until(lambda: output.exists() and output.stat().st_size>0 and not cache.get(f'transcoding_progress/{output}'))
assert probe(str(output))['streams'][0]['codec_name']=='h264'
assert not list(root.glob('.autolycus-transcode-*'))
print('PASS: two-slot concurrency guard, three queued bulk jobs cancelled, real queued encode and atomic output publication',flush=True)
client.close();cache.close()

# Individual file actions pass a download-root-relative path, unlike bulk jobs.
relative_output=source.with_name(source.stem+'_240p.mp4')
if relative_output.exists():relative_output.unlink()
result=api('POST','/files/transcode/start',params={'path':rel,'resolution':'240p'})
until(lambda:relative_output.exists() and relative_output.stat().st_size>0 and not cache.exists('transcoding_progress/'+str(relative_output)))
assert result['output_path']==str(relative_output)
print('PASS: individual transcode accepts the same relative path used by the file-menu action',flush=True)
