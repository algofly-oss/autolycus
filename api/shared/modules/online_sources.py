"""Bounded guest-provider lookup. No video decoding, media proxy or file storage.

Guest API protocol reference: https://github.com/faisaljs/Moviebox-API (MIT).
See /app/third_party/Moviebox-API-LICENSE.txt in the distributed container.
"""
import asyncio
import hashlib
import json
import re
import unicodedata
from urllib.parse import urlsplit, urlencode
import httpx

BASE='https://h5-api.aoneroom.com/wefeed-h5api-bff'
HEADERS={'User-Agent':'Mozilla/5.0','Origin':'https://moviebox.ph','Referer':'https://moviebox.ph/','Accept':'application/json'}
PLAYER_HOSTS={'mzfi.me','netfilm.world'}
SLOTS=asyncio.Semaphore(2)

def normalized(value):
    value=re.sub(r'\[[^\]]*\]','',value)
    return ''.join(c for c in unicodedata.normalize('NFKD',value).casefold() if c.isalnum())

def matches(item,title,year,kind):
    if normalized(str(item.get('title','')))!=normalized(title):return False
    if str(item.get('subjectType'))!=('2' if kind=='series' else '1'):return False
    date=str(item.get('releaseDate',''))
    return bool(year and date[:4]==str(year))

def media_url(value):
    if not isinstance(value,str) or len(value)>4096:return None
    try:
        u=urlsplit(value);host=u.hostname or '';port=u.port
    except ValueError:return None
    if u.scheme!='https' or u.username or u.password or port not in (None,443):return None
    return value if host.endswith('.hakunaymatata.com') else None

async def request_json(client,method,url,**kwargs):
    async with client.stream(method,url,**kwargs) as response:
        response.raise_for_status();data=bytearray()
        async for chunk in response.aiter_bytes(65536):
            data.extend(chunk)
            if len(data)>2*1024*1024:raise ValueError('Provider response exceeds limit')
        return json.loads(data),response.headers

async def lookup(title,year,kind,season=0,episode=0):
    if kind=='series' and (season<1 or episode<1):return []
    async with SLOTS:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10,connect=3),follow_redirects=False,headers=HEADERS) as client:
            _,headers=await request_json(client,'GET',BASE+'/home',params={'host':'moviebox.ph'})
            token=json.loads(headers.get('x-user','{}')).get('token')
            if not token:return []
            auth={'Authorization':'Bearer '+token}
            search,_=await request_json(client,'POST',BASE+'/subject/search',params={'host':'moviebox.ph'},headers=auth,json={'keyword':title,'page':1,'perPage':20})
            candidates=[row for row in (search.get('data') or {}).get('items',[])[:20] if isinstance(row,dict) and matches(row,title,year,kind)][:2]
            if not candidates:return []
            domain,_=await request_json(client,'GET',BASE+'/media-player/get-domain',params={'host':'moviebox.ph'},headers=auth)
            domain=str(domain.get('data') or '').rstrip('/');parsed=urlsplit(domain)
            if parsed.scheme!='https' or parsed.hostname not in PLAYER_HOSTS or parsed.netloc!=parsed.hostname:return []
            sources=[]
            for item in candidates:
                sid=str(item.get('subjectId') or '');detail=str(item.get('detailPath') or '')
                if not sid.isdigit() or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}',detail):continue
                ref=domain+'/spa/videoPlayPage/movies/'+detail+'?'+urlencode({'id':sid,'type':'/movie/detail','detailSe':season,'detailEp':episode,'lang':'en'})
                data,_=await request_json(client,'GET',domain+'/wefeed-h5api-bff/subject/play',params={'subjectId':sid,'se':season,'ep':episode,'detailPath':detail},headers={'Referer':ref})
                data=data.get('data') or {}
                if not data.get('hasResource'):continue
                for stream in data.get('streams',[])[:8]:
                    url=media_url(stream.get('url'))
                    if not url or str(stream.get('format','')).upper()!='MP4':continue
                    try:height=int(stream.get('resolutions') or 0);size=int(stream.get('size') or 0)
                    except (ValueError,TypeError):continue
                    if height not in (144,240,360,480,720,1080,1440,2160) or size<=0:continue
                    identity=f'{sid}:{season}:{episode}:{height}'
                    sources.append({'id':hashlib.sha256(identity.encode()).hexdigest()[:20],'provider':'MovieBox','label':str(item['title'])[:200],'quality':str(height)+'p','height':height,'size':size,'url':url,'format':'mp4','referer':ref})
            return sources[:16]
