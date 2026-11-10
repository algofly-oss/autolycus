"""Authenticated source discovery; no arbitrary-URL requests or media processing."""
import asyncio
import anyio
import json
import time
import hashlib
import secrets
import re
from starlette.responses import StreamingResponse
from fastapi import APIRouter,HTTPException,Request,Query
import httpx
from shared.factory import redis
from shared.modules.cinema_discovery import title_details
from shared.modules.online_sources import lookup,media_url,PLAYER_HOSTS
from urllib.parse import urlsplit
from ..auth.common import authenticate_user

router=APIRouter()

@router.get('/online/sources')
async def sources(request:Request,imdb_id:str=Query(...,regex=r'^tt\d{5,12}$'),kind:str=Query('movie',regex=r'^(movie|series)$'),season:int=Query(0,ge=0,le=999),episode:int=Query(0,ge=0,le=9999)):
    user=authenticate_user(request)
    key=f'online:sources:v2:{imdb_id}:{kind}:{season}:{episode}'
    cached=redis.get(key)
    if cached:return grant_sources(user,json.loads(cached))
    rate=f'online:lookup-rate:{user}:{int(time.time()//3600)}'
    count=redis.incr(rate)
    if count==1:redis.expire(rate,3600)
    if count>30:raise HTTPException(429,'Too many source lookups. Please try again later.')
    item=await title_details(imdb_id,kind)
    if not item:raise HTTPException(404,'Title metadata is unavailable.')
    try:
        entries=await asyncio.wait_for(lookup(item['title'],item['year'],kind,season,episode),timeout=35)
    except (httpx.HTTPError,ValueError,TypeError,KeyError,asyncio.TimeoutError):
        raise HTTPException(503,'The online provider is temporarily unavailable.')
    value={'sources':entries,'expires_in':120,'imdb_id':imdb_id,'season':season,'episode':episode,'title':item['title'],'year':item['year'],'kind':kind,'resolved_at':time.time()}
    encoded=json.dumps(value)
    # Independent bounded cache: no image/metadata entries are evicted here.
    lock=redis.lock('online:sources:cache-lock',timeout=3,blocking_timeout=.2)
    if len(encoded.encode())<=128*1024 and lock.acquire(blocking=True):
        try:
            redis.setex(key,120 if entries else 30,encoded)
            redis.zadd('online:sources:lru',{key:time.time()})
            while redis.zcard('online:sources:lru')>64:
                old=redis.zrange('online:sources:lru',0,0)
                if not old:break
                redis.delete(old[0]);redis.zrem('online:sources:lru',old[0])
        finally:
            try:lock.release()
            except Exception:pass
    return grant_sources(user,value)

STREAMS=asyncio.Semaphore(8)
REFRESH=asyncio.Lock()


def grant_sources(user,value):
    entries=[]
    lock=redis.lock('online:grant-lock',timeout=3,blocking_timeout=.2)
    if not lock.acquire(blocking=True):raise HTTPException(503,'Source lookup is busy. Please retry.')
    try:
        secret=redis.get('online:grant-secret')
        if not secret:
            redis.set('online:grant-secret',secrets.token_hex(32),nx=True)
            secret=redis.get('online:grant-secret')
        for source in value['sources']:
            raw=f'{secret}:{user}:{value["imdb_id"]}:{value["season"]}:{value["episode"]}:{source["id"]}'
            token=hashlib.sha256(raw.encode()).hexdigest()
            record={**value,'sources':None,'source':source,'user':str(user),'resolved_at':value.get('resolved_at',time.time())}
            redis.setex('online:grant:'+token,7200,json.dumps(record))
            redis.zadd('online:grants:lru',{token:time.time()})
            entries.append({k:v for k,v in source.items() if k not in ('url','referer')})
            entries[-1]['url']=f'/api/files/online/media/{token}'
        while redis.zcard('online:grants:lru')>256:
            old=redis.zrange('online:grants:lru',0,0)
            if not old:break
            token=old[0].decode() if isinstance(old[0],bytes) else old[0]
            redis.delete('online:grant:'+token);redis.zrem('online:grants:lru',token)
    finally:
        try:lock.release()
        except Exception:pass
    return {k:value[k] for k in ('imdb_id','season','episode','expires_in')}|{'sources':entries}


def grant(request,token):
    user=authenticate_user(request)
    if not re.fullmatch(r'[a-f0-9]{64}',token):raise HTTPException(404,'Source not found.')
    key='online:grant:'+token
    record=redis.get(key)
    if not record:raise HTTPException(410,'Source expired. Please choose it again.')
    record=json.loads(record)
    if record['user']!=str(user):raise HTTPException(403,'This source belongs to another account.')
    redis.expire(key,7200);redis.zadd('online:grants:lru',{token:time.time()})
    return record


@router.get('/online/media/{token}/info')
async def source_info(request:Request,token:str):
    record=grant(request,token);redis.setex('media-playback-active',45,1);source=record['source'];url=f'/api/files/online/media/{token}'
    return {'name':record['title']+'.mp4','size':source['size'],'type':'video/mp4','subtitles':[],'direct':False,'versions':[{'quality':'original','url':url,'name':record['title']+'.mp4','size':source['size']} ]}


async def refresh_source(token,record):
    if time.time()-record['resolved_at']<90:return record
    async with REFRESH:
        current=redis.get('online:grant:'+token)
        if not current:raise HTTPException(410,'Source expired.')
        record=json.loads(current)
        if time.time()-record['resolved_at']<90:return record
        try:
            sources=await asyncio.wait_for(lookup(record['title'],record['year'],record['kind'],record['season'],record['episode']),35)
        except (httpx.HTTPError,ValueError,TypeError,asyncio.TimeoutError):raise HTTPException(503,'Could not renew the source.')
        source=next((s for s in sources if s['id']==record['source']['id'] and s['size']==record['source']['size']),None)
        if not source:raise HTTPException(410,'This source is no longer available. Please choose another.')
        record.update(source=source,resolved_at=time.time())
        redis.setex('online:grant:'+token,7200,json.dumps(record));return record


def open_media_client():
    return httpx.AsyncClient(timeout=httpx.Timeout(20,connect=8),follow_redirects=False)


@router.get('/online/media/{token}')
async def media(request:Request,token:str):
    record=await refresh_source(token,grant(request,token));source=record['source']
    # Only provider-created targets are accepted, even if cached data is malformed.
    if not media_url(source['url']):raise HTTPException(502,'Invalid provider media URL.')
    ref=urlsplit(source.get('referer',''))
    if ref.scheme!='https' or ref.netloc not in PLAYER_HOSTS:raise HTTPException(502,'Invalid provider reference.')
    size=source['size'];range_header=request.headers.get('range');start,end=0,size-1
    if range_header:
        match=re.fullmatch(r'bytes=(\d*)-(\d*)',range_header)
        invalid=HTTPException(416,'Range not satisfiable.',headers={'Content-Range':f'bytes */{size}'})
        if not match or not any(match.groups()):raise invalid
        if match[1]:start=int(match[1]);end=min(int(match[2]),size-1) if match[2] else size-1
        elif int(match[2])>0:start=max(0,size-int(match[2]))
        else:raise invalid
        if start>end or start>=size:raise invalid
    try:await asyncio.wait_for(STREAMS.acquire(),2)
    except asyncio.TimeoutError:raise HTTPException(503,'All streaming connections are busy.')
    client=open_media_client()
    upstream=None
    cleaned=False
    async def cleanup():
        nonlocal cleaned
        if cleaned:return
        cleaned=True
        try:
            with anyio.move_on_after(2,shield=True):
                try:
                    if upstream is not None:await upstream.aclose()
                finally:await client.aclose()
        finally:STREAMS.release()
    try:
        upstream=await client.send(client.build_request('GET',source['url'],headers={'User-Agent':'Mozilla/5.0','Referer':source['referer'],'Range':f'bytes={start}-{end}','Accept-Encoding':'identity'}),stream=True)
        expected=f'bytes {start}-{end}/{size}'
        if upstream.status_code!=206 or upstream.headers.get('content-range')!=expected:
            raise HTTPException(502,'The provider could not supply this media range.')
        if upstream.headers.get('content-encoding','identity')!='identity':raise HTTPException(502,'Unsupported provider encoding.')
    except httpx.HTTPError:
        await cleanup();raise HTTPException(502,'The provider is unreachable. Please choose another source or try again.')
    except BaseException:
        await cleanup();raise
    async def chunks():
        remaining=end-start+1;marked=0
        try:
            async for chunk in upstream.aiter_raw(64*1024):
                if await request.is_disconnected():break
                if len(chunk)>remaining:raise RuntimeError('Provider exceeded requested range')
                if time.monotonic()-marked>=15:
                    redis.setex('media-playback-active',45,1);marked=time.monotonic()
                remaining-=len(chunk);yield chunk
            if remaining and not await request.is_disconnected():raise RuntimeError('Incomplete provider media range')
        finally:
            await cleanup()
    headers={'Accept-Ranges':'bytes','Content-Length':str(end-start+1),'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'}
    if range_header:headers['Content-Range']=expected
    return StreamingResponse(chunks(),status_code=206 if range_header else 200,media_type='video/mp4',headers=headers)
