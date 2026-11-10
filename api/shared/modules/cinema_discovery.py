"""Small public metadata cache; never requests or proxies movie streams."""
import asyncio,hashlib,json,re,time
from datetime import datetime,timezone
from urllib.parse import quote,urlparse
import requests
from shared.factory import redis

BASE='https://v3-cinemeta.strem.io'
SLOTS=asyncio.Semaphore(2)
ID=re.compile(r'^tt\d{5,12}$')
YOUTUBE=re.compile(r'^[A-Za-z0-9_-]{11}$')

def image_url(value):
    if not isinstance(value,str) or len(value)>1500:return None
    parsed=urlparse(value);host=parsed.hostname or ''
    return value if parsed.scheme=='https' and (host.endswith('.metahub.space') or host in {'image.tmdb.org','m.media-amazon.com','images.metahub.space','live.metahub.space'}) else None

def strings(value,limit=8):
    if isinstance(value,str):value=[v.strip() for v in value.split(',')]
    return [str(v)[:120] for v in (value or []) if isinstance(v,str)][:limit] if isinstance(value,list) else []

def normalize(meta,kind):
    key=meta.get('imdb_id') or meta.get('id')
    if not isinstance(key,str) or not ID.fullmatch(key):return None
    trailers=[]
    for value in (meta.get('trailerStreams') or [])+(meta.get('trailers') or []):
        if not isinstance(value,dict):continue
        video=value.get('ytId') or value.get('source')
        if isinstance(video,str) and YOUTUBE.fullmatch(video) and not any(t['id']==video for t in trailers):trailers.append({'id':video,'name':str(value.get('title') or value.get('type') or 'Official trailer')[:100]})
    try:rating=float(meta.get('imdbRating') or 0)
    except (TypeError,ValueError):rating=0
    year=re.search(r'\d{4}',str(meta.get('year') or meta.get('releaseInfo') or ''))
    return {'id':key,'imdb_id':key,'tmdb_id':meta.get('moviedb_id'),'title':str(meta.get('name') or 'Untitled')[:200],'kind':'series' if kind=='series' else 'movie','year':int(year.group()) if year else None,
      'overview':str(meta.get('description') or '')[:2400],'genres':strings(meta.get('genres') or meta.get('genre'),6),'cast':strings(meta.get('cast'),10),'directors':strings(meta.get('director'),3),
      'runtime':str(meta.get('runtime') or '')[:40],'rating':rating if 0<rating<=10 else None,'rating_source':'IMDb','awards':str(meta.get('awards') or '')[:300],
      'poster':image_url(meta.get('poster')),'background':image_url(meta.get('background')),'logo':image_url(meta.get('logo')),'trailers':trailers[:6],
      'released':str(meta.get('released') or '')[:32],'status':str(meta.get('status') or '')[:80],'owned':False,'files':[]}

def fetch_json(path):
    with requests.get(BASE+path,timeout=(3,7),stream=True,headers={'User-Agent':'Autolycus/1.0 (metadata)'}) as response:
        response.raise_for_status();body=bytearray()
        for chunk in response.iter_content(65536):
            body.extend(chunk)
            if len(body)>2*1024*1024:raise ValueError('Metadata response exceeds limit')
        return json.loads(body)

def store(key,value,ttl,limit=256):
    encoded=json.dumps(value);size=len(encoded.encode())
    if size>2*1024*1024:return
    lock=redis.lock('cinema:metadata:cache-lock',timeout=3,blocking_timeout=.3)
    if not lock.acquire(blocking=True):return
    try:
        index='cinema:metadata:lru';sizes='cinema:metadata:sizes';total_key='cinema:metadata:bytes'
        previous=int(redis.hget(sizes,key) or 0)
        redis.setex(key,ttl,encoded);redis.zadd(index,{key:time.time()});redis.hset(sizes,key,size)
        total=redis.incrby(total_key,size-previous)
        while redis.zcard(index)>limit or total>16*1024*1024:
            oldest=redis.zrange(index,0,0)
            if not oldest:break
            old=oldest[0];removed=int(redis.hget(sizes,old) or 0)
            redis.delete(old);redis.zrem(index,old);redis.hdel(sizes,old);total=redis.incrby(total_key,-removed)
    finally:
        try:lock.release()
        except Exception:pass

async def title_details(imdb_id,kind):
    key=f'cinema:detail:v1:{kind}:{imdb_id}';cached=redis.get(key)
    if cached:return json.loads(cached)
    async with SLOTS:
        try:
            meta=(await asyncio.to_thread(fetch_json,f'/meta/{kind}/{imdb_id}.json')).get('meta') or {}
            value=normalize(meta,kind)
            if value and not value['overview']:
                try:
                    from .search_posters import _imdb_title_details
                    details=await asyncio.to_thread(_imdb_title_details,imdb_id,int(time.time()//3600))
                    value['overview']=details.get('overview') or ''
                except (requests.RequestException,ValueError,TypeError):pass
            store(key,value,7*86400 if value and value['overview'] else 900)
            return value
        except (requests.RequestException,ValueError,TypeError):store(key,None,300);return None

async def catalog(kind,sort):
    key=f'cinema:catalog-public:v1:{kind}:{sort}';cached=redis.get(key)
    if cached:return json.loads(cached)
    async with SLOTS:
        try:
            data=await asyncio.to_thread(fetch_json,f'/catalog/{kind}/{sort}.json')
            items=[item for meta in data.get('metas',[])[:60] if isinstance(meta,dict) for item in [normalize(meta,kind)] if item]
            store(key,items,3600);return items
        except (requests.RequestException,ValueError,TypeError):store(key,[],120);return []

async def discovery_shelves():
    movies,series,new_movies,new_series,top_movies,top_series=await asyncio.gather(catalog('movie','top'),catalog('series','top'),catalog('movie','year'),catalog('series','year'),catalog('movie','imdbRating'),catalog('series','imdbRating'))
    today=datetime.now(timezone.utc).date().isoformat()
    new=sorted((item for item in new_movies+new_series if not item['released'] or item['released'][:10]<=today),key=lambda item:item['released'] or str(item['year'] or ''),reverse=True)
    award=lambda item:bool(re.search(r'oscar|bafta|golden globe|primetime emmy|academy award',item['awards'],re.I))
    return [{'id':key,'title':title,'items':items[:24]} for key,title,items in [
      ('trending-movies','Trending movies',movies[:24]),('trending-series','Trending TV shows',series[:24]),('new','New releases',new),
      ('popular-movies','Popular movies',movies[16:]),('top-movies','Top rated movies',sorted(top_movies,key=lambda x:x['rating'] or 0,reverse=True)),
      ('top-series','Top rated TV shows',sorted(top_series,key=lambda x:x['rating'] or 0,reverse=True)),
      ('award-movies','Award-worthy movies',[item for item in top_movies if award(item)]),('award-series','Award-worthy TV shows',[item for item in top_series if award(item)])] if items]

async def search_titles(query):
    key='cinema:search:v1:'+hashlib.sha256(query.casefold().encode()).hexdigest();cached=redis.get(key)
    if cached:return json.loads(cached)
    async def search(kind):
        async with SLOTS:
            try:
                data=await asyncio.to_thread(fetch_json,f'/catalog/{kind}/top/search={quote(query,safe="")}.json')
                return [item for meta in data.get('metas',[])[:24] if isinstance(meta,dict) for item in [normalize(meta,kind)] if item]
            except (requests.RequestException,ValueError,TypeError):return []
    items=sum(await asyncio.gather(search('movie'),search('series')),[]);store(key,items,900);return items
