"""Disposable API regression: public player flags, exact-file scope and downloads."""
import json,shutil
from pathlib import Path
from urllib.parse import quote
import requests
from pymongo import MongoClient
BASE='http://127.0.0.1';s=requests.Session();USER='public-player@example.test';PASSWORD='Public-player-123!'
for action in ['signup','signin']:s.post(BASE+'/api/auth/'+action,json={'name':'Public fixture','username':USER,'password':PASSWORD}).raise_for_status()
h=json.loads(Path('/run/autolycus/health.json').read_text());db=MongoClient(h['mongo_uri'])[h['database']];uid=str(db.users.find_one({'username':USER})['_id'])
root=Path('/downloads')/uid/'public-fixture';root.mkdir(parents=True,exist_ok=True)
files=[]
for name,source in [('Shared.Movie.2025.mp4','tracks.mp4'),('Shared.Series.S01E02.mkv','embedded.mkv')]:
 file=root/name;shutil.copyfile(Path('/downloads/playback-fixtures')/source,file)
 payload={'path':str(file)}
 if name.endswith('.mkv'):payload['key']='public-player-mkv-'+uid[-8:]
 response=s.post(BASE+'/api/files/generate-public-url',json=payload);response.raise_for_status();key=response.json()['key']
 url=BASE+'/api/files/public/'+quote(key,safe='');files.append({'path':str(file.relative_to('/downloads')),'key':key,'url':url,'name':name})
 raw=requests.get(url,headers={'Range':'bytes=0-31'});assert raw.status_code==206 and raw.content==file.read_bytes()[:32]
 html=requests.get(BASE+'/watch?key='+quote(key,safe=''));assert html.status_code==200 and '__NEXT_DATA__' in html.text
 for query in ['download=1','download=true']:
  result=requests.get(url+'?'+query,stream=True);assert result.status_code==200 and 'attachment' in result.headers.get('Content-Disposition','');result.close()
 info=requests.get(BASE+'/api/files/public-playback/'+quote(key,safe='')+'/info');info.raise_for_status();data=info.json()
 assert uid not in info.text and str(root) not in info.text and len(data['versions'])==1,data
 assert data['name']==name
 assert requests.get(BASE+'/api/files/stream',params={'path':str(file.relative_to('/downloads'))}).status_code>=400
 assert requests.post(BASE+'/api/files/public-playback/'+quote(key,safe='')+'/offer',json={'sdp':'bad'},headers={'Origin':'https://foreign.invalid'}).status_code==403

sidecar=root/'Shared.Movie.2025.en.srt';sidecar.write_text('1\n00:00:00,000 --> 00:00:35,000\nPublic subtitle fixture\n')
(root/'private.srt').write_text('Private subtitle')
prefix=BASE+'/api/files/public-playback/'+quote(files[0]['key'],safe='')
assert requests.get(prefix+'/subtitle',params={'name':sidecar.name}).status_code==200
assert requests.get(prefix+'/subtitle',params={'name':'private.srt'}).status_code==404
assert requests.get(prefix+'/subtitle',params={'name':'../private.srt'}).status_code==404
# Revocation affects metadata, subtitles, previews, raw bytes and new offers.
db.public_urls.update_one({'title':files[0]['key']},{'$set':{'active':False}})
for suffix in ['/info','/subtitle?name='+quote(sidecar.name),'/preview','/preview-image']:assert requests.get(prefix+suffix).status_code==404,suffix
assert requests.get(files[0]['url'],allow_redirects=False).status_code==404
db.public_urls.update_one({'title':files[0]['key']},{'$set':{'active':True}})
Path('/data/public-player-fixture.json').write_text(json.dumps({'files':files,'username':USER,'password':PASSWORD}))
print('PASS: direct public watch page, download precedence, byte ranges, single-file metadata scope, sidecar confinement, private endpoint authentication and revocation',flush=True)
