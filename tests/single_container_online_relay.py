"""Disposable app: byte-exact relay ranges, provider headers, grants and cleanup."""
import asyncio,json,os,re
import anyio
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
 from router.auth.common import authenticate_user
 from starlette.requests import Request
 scope={'type':'http','headers':[(b'cookie',s.cookies.get_dict().popitem()[0].encode()+b'='+next(iter(s.cookies.get_dict().values())).encode())]}
 user=authenticate_user(Request(scope))
 body=b'0123456789abcdefghijklmnopqrstuvwxyz';seen=[]
 class Bytes(httpx.AsyncByteStream):
  def __init__(self,data):self.data=data
  async def __aiter__(self):yield self.data
 def upstream(request):
  seen.append(request)
  assert request.headers['referer']=='https://mzfi.me/fixture'
  assert 'cookie' not in request.headers and 'authorization' not in request.headers
  start,end=map(int,re.fullmatch(r'bytes=(\d+)-(\d+)',request.headers['range']).groups())
  return httpx.Response(206,headers={'Content-Range':f'bytes {start}-{end}/{len(body)}'},stream=Bytes(body[start:end+1]))
 old=online.open_media_client
 clients=[]
 def factory():
  client=httpx.AsyncClient(transport=httpx.MockTransport(upstream));clients.append(client);return client
 online.open_media_client=factory
 value={'imdb_id':'tt0910970','title':'Fixture','year':2008,'kind':'movie','season':0,'episode':0,'expires_in':120,'sources':[{'id':'relay-fixture','label':'Fixture','size':len(body),'url':'https://cdn.hakunaymatata.com/a.mp4','referer':'https://mzfi.me/fixture'}]}
 public=online.grant_sources(user,value);url=public['sources'][0]['url'];token=url.rsplit('/',1)[-1]
 assert 'referer' not in public['sources'][0] and 'hakunaymatata' not in json.dumps(public)
 try:
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://127.0.0.1') as client:
   assert (await client.get(url)).status_code==400
   client.cookies.update(s.cookies.get_dict())
   info=await client.get(url+'/info');assert info.status_code==200 and info.json()['size']==len(body)
   for header,expected in [('bytes=3-9',body[3:10]),('bytes=-4',body[-4:]),('bytes=30-',body[30:])]:
    response=await client.get(url,headers={'Range':header});assert response.status_code==206,response.text
    assert response.content==expected and int(response.headers['content-length'])==len(expected)
   response=await client.get(url);assert response.status_code==200 and response.content==body
   count=len(seen)
   for invalid in ['bytes=99-100','bytes=9-3','bytes=0-1,4-5','bytes=-0']:
    assert (await client.get(url,headers={'Range':invalid})).status_code==416
   assert len(seen)==count
   async def receive():return {'type':'http.request','body':b'','more_body':False}
   response=await online.media(Request(scope,receive=receive),token)
   assert await response.body_iterator.__anext__()==body
   assert online.STREAMS._value==7
   with anyio.CancelScope() as cancelled:
    cancelled.cancel()
    await response.body_iterator.aclose()
   assert online.STREAMS._value==8 and clients[-1].is_closed
   def unavailable(request):raise httpx.ConnectTimeout('fixture CDN unavailable')
   online.open_media_client=lambda:httpx.AsyncClient(transport=httpx.MockTransport(unavailable))
   response=await client.get(url,headers={'Range':'bytes=0-3'})
   assert response.status_code==502 and 'provider' in response.json()['detail'].lower()
   assert online.STREAMS._value==8
   record=json.loads(redis.get('online:grant:'+token));record['user']='other-user';redis.setex('online:grant:'+token,30,json.dumps(record))
   assert (await client.get(url)).status_code==403
   assert online.STREAMS._value==8
   assert redis.exists('media-playback-active')
   print('PASS: byte-exact partial/suffix/open/full responses; invalid ranges; required provider headers; no credentials forwarded; authenticated account-bound opaque grants; stream slots released even under cancellation; preview contention marker')
 finally:
  online.open_media_client=old;redis.delete('online:grant:'+token);redis.zrem('online:grants:lru',token)
asyncio.run(check())
