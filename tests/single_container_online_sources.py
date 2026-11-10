import asyncio,json,os
from pathlib import Path
import requests
pid=Path('/run/autolycus/services/api').read_text().strip()
for entry in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0'):
 if b'=' in entry:
  k,v=entry.split(b'=',1);os.environ[k.decode()]=v.decode()
import httpx
f=json.loads(Path('/data/cinema-fixture.json').read_text());s=requests.Session();s.post('http://127.0.0.1/api/auth/signin',json={'username':f['username'],'password':f['password']}).raise_for_status()
async def check():
 from main import app
 from router.files import online
 from shared.factory import redis
 calls=[]
 async def metadata(imdb,kind):return {'title':'WALL·E','year':2008}
 async def provider(title,year,kind,season,episode):calls.append((title,year,kind,season,episode));return [{'id':'fixture','url':'https://cdn.hakunaymatata.com/a.mp4'}]
 old_meta,old_provider=online.title_details,online.lookup;online.title_details,online.lookup=metadata,provider
 key='online:sources:v2:tt0910970:movie:0:0';redis.delete(key)
 try:
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://127.0.0.1') as client:
   r=await client.get('/api/files/online/sources',params={'imdb_id':'tt0910970'});assert r.status_code==400
   client.cookies.update(s.cookies.get_dict())
   r=await client.get('/api/files/online/sources',params={'imdb_id':'http://127.0.0.1/'});assert r.status_code==422
   for _ in range(2):
    r=await client.get('/api/files/online/sources',params={'imdb_id':'tt0910970','title':'Forged title','year':2026});assert r.status_code==200,r.text
   assert calls==[('WALL·E',2008,'movie',0,0)],calls
   assert 0<redis.ttl(key)<=120
   print('PASS: real-session authentication, invalid ID rejection, authoritative title/year, bounded TTL and cached lookup reuse')
 finally:
  online.title_details,online.lookup=old_meta,old_provider;redis.delete(key);redis.zrem('online:sources:lru',key)
asyncio.run(check())
