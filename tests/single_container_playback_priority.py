"""All player info modes defer preview work before a frame or RTC lease exists."""
import asyncio,json,os,secrets
from pathlib import Path
import requests,httpx
pid=Path('/run/autolycus/services/api').read_text().strip()
for entry in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0'):
 if b'=' in entry:
  k,v=entry.split(b'=',1);os.environ[k.decode()]=v.decode()
f=json.loads(Path('/data/cinema-fixture.json').read_text());layout=json.loads(Path('/data/avatar-lan-layout.json').read_text());s=requests.Session();s.post('http://127.0.0.1/api/auth/signin',json={'username':f['username'],'password':f['password']}).raise_for_status()
async def check():
 from main import app
 from shared.factory import db,redis
 from shared.env import SESSION_COOKIE_NAME
 from router.files import online
 from router.torrent.preview import previews
 from tasks import media_previews
 from celery.exceptions import Retry
 user=redis.get(s.cookies[SESSION_COOKIE_NAME]);key='priority-'+secrets.token_hex(8)
 inserted=await db.public_urls.insert_one({'title':key,'active':True,'path':layout['path']})
 source=online.grant_sources(user,{'imdb_id':'tt0910970','title':'Fixture','year':2008,'kind':'movie','season':0,'episode':0,'expires_in':120,'sources':[{'id':'priority','label':'Fixture','url':'https://cdn.hakunaymatata.com/a.mp4','referer':'https://mzfi.me/fixture','size':1024}]})['sources'][0]['url']
 old_info=previews.file_info
 def preview_info(actor,token,index):
  assert actor==user.decode();return {'name':'fixture.mp4','size':1024}
 previews.file_info=preview_info
 try:
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://127.0.0.1',cookies=s.cookies.get_dict()) as client:
   routes=['/api/files/playback/info?path='+layout['path'],'/api/files/public-playback/'+key+'/info',source+'/info','/api/torrent/preview/'+'a'*48+'/file/0/info']
   for route in routes:
    redis.delete('media-playback-active');r=await client.get(route);assert r.status_code==200,r.text
    assert 40<=redis.ttl('media-playback-active')<=45,route
  called=[];original=media_previews.generate_sprite
  media_previews.generate_sprite=lambda *a,**k:called.append(True)
  try:
   try:media_previews.generate_preview.run('/downloads/'+layout['path'])
   except Retry:pass
   else:raise AssertionError('Preview task did not defer')
   assert not called
  finally:media_previews.generate_sprite=original
  print('PASS: private/public/online/torrent player info marks startup immediately; thumbnail task defers before generation; no frame or lease renewal required')
 finally:
  previews.file_info=old_info;await db.public_urls.delete_one({'_id':inserted.inserted_id});token=source.rsplit('/',1)[-1];redis.delete('online:grant:'+token);redis.zrem('online:grants:lru',token)
asyncio.run(check())
