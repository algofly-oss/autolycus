"""Generated records/media for an explicitly marked disposable container only."""
import json,time,subprocess,datetime,os,asyncio
from pathlib import Path
import requests
from pymongo import MongoClient
from bson import ObjectId
assert Path('/data/mobile-review-isolated').exists(), 'Requires disposable fixture marker'
s=requests.Session();base='http://127.0.0.1'
for i in range(50):
 try:
  if s.get(base+'/api/ping',timeout=1).status_code==200:break
 except requests.RequestException:pass
 time.sleep(1)
username='mobile-review@example.test';password='Mobile-review-fixture-123!'
for action in ['signup','signin']:s.post(base+'/api/auth/'+action,json={'name':'Mobile review','username':username,'password':password}).raise_for_status()
h=json.loads(Path('/run/autolycus/health.json').read_text());db=MongoClient(h['mongo_uri'])[h['database']];user=db.users.find_one({'username':username});uid=str(user['_id']);root=Path('/downloads')/uid/'review';root.mkdir(parents=True,exist_ok=True)
video=root/'Review.Movie.2024.mp4'
if not video.exists():subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=s=320x180:r=15','-f','lavfi','-i','sine=frequency=440','-t','30','-c:v','libx264','-threads','1','-preset','ultrafast','-c:a','aac','-movflags','+faststart',str(video)],check=True)
db.torrents.delete_many({'user_id':user['_id']})
rows=[]
for i in range(260):
 path=root/f'Collection.{i:04d}';path.mkdir(exist_ok=True)
 rows.append({'user_id':user['_id'],'id':'review-'+str(i),'info_hash':f'{i+10000:040x}','name':f'Collection {i:04d}','created_at':datetime.datetime(2025,1,1)+datetime.timedelta(seconds=i),'save_dir':str(path),'total_bytes':1,'downloaded_bytes':1,'download_speed':0,'progress':100,'is_finished':True,'is_paused':True})
db.torrents.insert_many(rows)
# Index real fixture records through the application's own search index helper.
pid=Path('/run/autolycus/services/api').read_text().strip()
for entry in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0'):
 if b'=' in entry:
  k,v=entry.split(b'=',1);os.environ[k.decode()]=v.decode()
from shared.modules.meilisearch_client import meili
idx=meili.ensure_file_index()
docs=[{'id':'review-'+str(i),'user_id':uid,'torrent_id':row['info_hash'],'torrent_title':row['name'],'item_type':'directory','is_torrent_root':True,'name':row['name'],'relative_path':str(Path(row['save_dir']).relative_to('/downloads')),'directory_path':str(Path(row['save_dir']).relative_to('/downloads')),'last_modified_ts':i,'size':1,'content':row['name']} for i,row in enumerate(rows)]
task=idx.update_documents(docs);idx.wait_for_task(task.task_uid,timeout_in_ms=30000)
Path('/data/mobile-fixture.json').write_text(json.dumps({'username':username,'password':password,'path':str(video.relative_to('/downloads')),'directory':str(root.relative_to('/downloads'))}))
print('PASS: isolated fake account, generated A/V file, 260 database collections and matching indexed search records')
