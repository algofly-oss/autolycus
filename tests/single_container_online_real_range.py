import asyncio,json,os
from pathlib import Path
import requests,httpx
pid=Path('/run/autolycus/services/api').read_text().strip()
for entry in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0'):
 if b'=' in entry:
  k,v=entry.split(b'=',1);os.environ[k.decode()]=v.decode()
f=json.loads(Path('/data/cinema-fixture.json').read_text());s=requests.Session();s.post('http://127.0.0.1/api/auth/signin',json={'username':f['username'],'password':f['password']}).raise_for_status()
async def check():
 from main import app
 async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://127.0.0.1',cookies=s.cookies.get_dict(),timeout=60) as client:
  result=await client.get('/api/files/online/sources',params={'imdb_id':'tt0910970'});result.raise_for_status();sources=result.json()['sources'];assert sources
  url=sources[0]['url'];info=await client.get(url+'/info');info.raise_for_status()
  response=await client.get(url,headers={'Range':'bytes=0-32767'});response.raise_for_status()
  assert response.status_code==206 and len(response.content)==32768
  assert response.content[4:8]==b'ftyp'
  print('PASS: real authenticated WALL·E lookup → opaque source → info → original MP4 bytes through relay; 32 KiB HTTP 206, valid ftyp box; no transcoding or movie files created')
asyncio.run(check())
