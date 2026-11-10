"""Disposable API: real metadata, selected file transfer and persisted resume choice."""
import asyncio,json,os,tempfile,time,shutil,hashlib
from pathlib import Path
import requests,httpx,libtorrent as lt
pid=Path('/run/autolycus/services/api').read_text().strip()
for entry in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0'):
 if b'=' in entry:
  k,v=entry.split(b'=',1);os.environ[k.decode()]=v.decode()
f=json.loads(Path('/data/cinema-fixture.json').read_text());login=requests.Session();login.post('http://127.0.0.1/api/auth/signin',json={'username':f['username'],'password':f['password']}).raise_for_status()
async def check():
 from main import app
 from shared.factory import db
 from shared.modules.torrent_preview import previews
 import shared.modules.libtorrentx as sdk
 from router.torrent import resume
 Native=sdk.LibTorrentSession;instances=[]
 class Tracking(Native):
  def __init__(self,**kw):
   super().__init__(**kw);instances.append(self)
   self.session.apply_settings({'enable_dht':False,'enable_lsd':False,'enable_upnp':False,'enable_natpmp':False,'listen_interfaces':'127.0.0.1:0'})
  def add_torrent(self,*args,**kw):
   wrapper=super().add_torrent(*args,**kw)
   # Isolate poster/socket/background-index callbacks from this route contract test.
   wrapper.set_callback=lambda *a,**k:None
   return wrapper
 sdk.LibTorrentSession=Tracking;old_resume=resume.LibTorrentSession;resume.LibTorrentSession=Tracking
 user=await db.users.find_one({'username':f['username']});uid=str(user['_id']);token=None;info_hash=None
 try:
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'Course').mkdir();storage=lt.file_storage();wanted=os.urandom(512*1024)
   for name,data in [('a-unused.bin',os.urandom(512*1024)),('b-wanted.mp4',wanted)]:
    (root/'Course'/name).write_bytes(data);storage.add_file('Course/'+name,len(data))
   creator=lt.create_torrent(storage,16384);lt.set_piece_hashes(creator,str(root));ti=lt.torrent_info(lt.bencode(creator.generate()));magnet=lt.make_magnet_uri(ti);info_hash=str(ti.info_hashes().v1)
   seed=lt.session({'listen_interfaces':'127.0.0.1:0','enable_dht':False,'enable_lsd':False,'enable_upnp':False,'enable_natpmp':False});seed.add_torrent({'ti':ti,'save_path':str(root),'flags':lt.torrent_flags.seed_mode})
   async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://127.0.0.1',cookies=login.cookies.get_dict()) as client:
    response=await client.post('/api/torrent/preview',json={'magnet':magnet});assert response.status_code==200,response.text;token=response.json()['id']
    previews.engine.session.apply_settings({'enable_dht':False,'enable_lsd':False});previews.leases[token]['handle'].connect_peer(('127.0.0.1',seed.listen_port()))
    for _ in range(200):
     result=(await client.get('/api/torrent/preview/'+token)).json()
     if result.get('status')=='ready':break
     await asyncio.sleep(.1)
    else:raise AssertionError('Metadata timeout')
    assert result['payload_downloaded']==0
    media_url='/api/torrent/preview/'+token+'/file/1'
    response=await client.get(media_url+'/info');assert response.status_code==200 and response.json()['size']==len(wanted)
    response=await client.get(media_url,headers={'Range':'bytes=7000-17000'});assert response.status_code==206 and response.content==wanted[7000:17001]
    response=await client.get(media_url,headers={'Range':'bytes=-1024'});assert response.status_code==206 and response.content==wanted[-1024:]
    assert (await client.get(media_url,headers={'Range':'bytes=9999999-'})).status_code==416
    from router.torrent.preview import preview_streams
    assert preview_streams._value==4
    for invalid in [[],[999],[True],[1.1]]:
     response=await client.post('/api/torrent/preview/'+token+'/download',json={'indices':invalid});assert response.status_code in (409,422),response.text
    response=await client.post('/api/torrent/preview/'+token+'/download',json={'indices':[1]});assert response.status_code==200,response.text
    wrapper=instances[-1].handles[info_hash];wrapper.handle.connect_peer(('127.0.0.1',seed.listen_port()))
    for _ in range(200):
     if wrapper.handle.status().is_finished:break
     await asyncio.sleep(.1)
    else:raise AssertionError('Selected download timeout')
    assert hashlib.sha256((Path(wrapper.save_dir)/'Course/b-wanted.mp4').read_bytes()).digest()==hashlib.sha256(wanted).digest()
    assert not (Path(wrapper.save_dir)/'Course/a-unused.bin').exists()
    row=await db.torrents.find_one({'info_hash':info_hash,'user_id':user['_id']});assert row['selected_files']==[1] and row['torrent_metadata']
    response=await client.get('/api/torrent/all');assert response.status_code==200,response.text;assert all('torrent_metadata' not in r for r in response.json()['data'])
    assert (await client.post('/api/torrent/preview/'+token+'/download',json={'indices':[1]})).status_code==409
    instances[-1]._stop(info_hash)
    await db.torrents.update_one({'_id':row['_id']},{'$set':{'is_paused':True,'is_finished':False}})
    response=await client.post('/api/torrent/resume',params={'info_hash':info_hash});assert response.status_code==200,response.text
    assert instances[-1].handles[info_hash].handle.get_file_priorities()==[0,1]
    print('PASS: metadata-only API; strict selection validation; exact HTTP preview ranges and suffix; real selected bytes; persisted metadata/indices; no metadata blob in list JSON; duplicate prevention; API resume keeps selection')
 finally:
  sdk.LibTorrentSession=Native;resume.LibTorrentSession=old_resume
  for instance in instances:
   for key in list(instance.handles):instance._stop(key)
  if token:
   try:previews.close(uid,token)
   except Exception:pass
  previews.shutdown()
  if info_hash:
   await db.torrents.delete_many({'info_hash':info_hash,'user_id':user['_id']});shutil.rmtree(Path('/downloads')/uid/info_hash,ignore_errors=True)
asyncio.run(check())
