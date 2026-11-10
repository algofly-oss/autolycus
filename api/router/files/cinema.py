"""Account-scoped cinematic catalog. Reads names/stats, never probes media."""
import asyncio
import hashlib
import json
import os
import re
import time
from pathlib import Path
from bson import ObjectId
from fastapi import APIRouter, Request
from shared.factory import db, redis
from shared.modules.media_filename import media_filename, file_presentation
from shared.modules.media_metadata import media_metadata_for_relative_paths, media_metadata_for_torrent_ids
from shared.modules.media_profiles import profile_id
from shared.modules.folder_watch import combine
from ..auth.common import authenticate_user
from .watch_progress import collection as progress_collection, visible

router = APIRouter()
VIDEO = {'.mp4','.mkv','.avi','.mov','.webm','.m4v','.ts','.m2ts','.ogv'}
VARIANT = re.compile(r'_(144|240|360|480|720|1080|1440|2160)p$',re.I)


def scan_library(user, excluded):
    root=Path(os.getenv('DOWNLOAD_PATH','/downloads')).resolve()
    account=root/user
    if account.is_symlink() or not account.is_dir():return [],False
    pending=[(account,0)];files=[];visited=0;limited=False;started=time.monotonic()
    while pending:
        directory,depth=pending.pop()
        if depth>16:limited=True;continue
        try:
            with os.scandir(directory) as items:
                for entry in items:
                    visited+=1
                    if visited>20000 or len(files)>=4000 or time.monotonic()-started>3:
                        return files,True
                    if entry.name.startswith('.') or entry.is_symlink():continue
                    path=Path(entry.path);relative=path.relative_to(root)
                    if len(relative.parts)>1 and relative.parts[1] in excluded:continue
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name.casefold() not in {'sample','samples','extras','trailers','.thumbs'}:pending.append((path,depth+1))
                    elif path.suffix.lower() in VIDEO and entry.is_file(follow_symlinks=False):
                        if re.search(r'(?:^|[ ._-])sample(?:[ ._-]|$)',path.stem,re.I):continue
                        stat=entry.stat(follow_symlinks=False)
                        if stat.st_size:files.append({'path':str(relative),'name':entry.name,'modified':stat.st_mtime,'size':stat.st_size})
        except OSError:continue
    stems={str(Path(f['path']).with_suffix('')) for f in files}
    return [f for f in files if not (VARIANT.search(Path(f['path']).stem) and str(Path(f['path']).with_suffix('')).rsplit('_',1)[0] in stems)],limited


def number(value, default=0):
    if isinstance(value,list):value=value[0] if value else default
    match=re.search(r'\d+',str(value or ''))
    return int(match.group()) if match else default


def catalog_groups(files, path_metadata, torrent_metadata):
    groups={}
    for file in files:
        path=Path(file['path']);parts=path.parts
        metadata=path_metadata.get(file['path']) or torrent_metadata.get(parts[1] if len(parts)>1 else '') or {}
        info=media_filename(file['path']);presentation=file_presentation(file['path'])
        episode=presentation['episode_info'];kind='series' if episode else 'movie'
        title=metadata.get('title') or info['title'];year=number(metadata.get('year') or info.get('year')) or None
        identity=re.sub(r'[^\w]+',' ',title.casefold()).strip()+':'+str(year or '')+':'+kind
        key=hashlib.sha1(identity.encode()).hexdigest()[:16]
        resolution=metadata.get('quality',{}).get('resolution') or info.get('resolution') or ''
        entry={**file,**presentation,'resolution':str(resolution),'season':episode.get('season') or 0 if episode else 0,'episode':episode.get('episode') or 0 if episode else 0}
        group=groups.setdefault(key,{'id':key,'title':title,'year':year,'kind':kind,'poster':metadata.get('poster_url'),'overview':metadata.get('overview') or '', 'rating':metadata.get('vote_average'),'imdb_id':metadata.get('imdb_id'),'tmdb_id':metadata.get('tmdb_id'),'owned':True,'files':[],'added':0})
        group['files'].append(entry);group['added']=max(group['added'],file['modified'])
        if not group['poster'] and metadata.get('poster_url'):group['poster']=metadata['poster_url']
    result=[]
    for group in groups.values():
        group['files'].sort(key=lambda f:(f['season'],f['episode'],-number(f['resolution']),f['name'].casefold()))
        if group['kind']=='series':
            episodes={}
            for file in group['files']:episodes.setdefault((file['season'],file['episode']),file)
            group['files']=list(episodes.values())
        group['path']=group['files'][0]['path'];group['resolution']=group['files'][0]['resolution']
        result.append(group)
    return sorted(result,key=lambda g:g['added'],reverse=True)


@router.get('/cinema')
async def cinema_catalog(request: Request):
    user=authenticate_user(request).decode();selected=await profile_id(request,user)
    key='cinema:catalog:v2:'+user
    cached=redis.get(key)
    if cached:
        payload=json.loads(cached)
    else:
        unfinished=await db.torrents.find({'user_id':ObjectId(user),'is_finished':False},{'info_hash':1,'url_hash':1}).to_list(length=5000)
        excluded={str(doc[field]) for doc in unfinished for field in ('info_hash','url_hash') if doc.get(field)}
        files,limited=await asyncio.to_thread(scan_library,user,excluded)
        paths=[f['path'] for f in files];ids=list({Path(p).parts[1] for p in paths if len(Path(p).parts)>1})
        by_path,by_torrent=await asyncio.gather(media_metadata_for_relative_paths(db,user,paths),media_metadata_for_torrent_ids(db,user,ids))
        payload={'items':await asyncio.to_thread(catalog_groups,files,by_path,by_torrent),'limited':limited}
        encoded=json.dumps(payload)
        if len(encoded)<4*1024*1024:redis.setex(key,90,encoded)
    paths=[f['path'] for group in payload['items'] for f in group['files']]
    docs=await (await progress_collection()).find({'user_id':user,'profile_id':selected,'path':{'$in':paths}}).to_list(length=4000)
    progress={doc['path']:{**visible(doc),'updated':doc['updated_at'].timestamp()} for doc in docs}
    for group in payload['items']:
        recent=sorted((progress[f['path']] for f in group['files'] if f['path'] in progress),key=lambda p:p['updated'],reverse=True)
        group['watch_progress']=combine(group['id'],[[f['path']] for f in group['files']],[progress[f['path']] for f in group['files'] if f['path'] in progress])
        group['progress']=recent[0] if recent else None
        group['resume_path']=group['progress']['path'] if recent else group['path']
        if recent and recent[0]['completed'] and group['kind']=='series':
            index=next((i for i,f in enumerate(group['files']) if f['path']==recent[0]['path']),-1)
            if 0<=index<len(group['files'])-1:group['resume_path']=group['files'][index+1]['path'];group['next_episode']=True
        for file in group['files']:file['progress']=progress.get(file['path'])
    return payload

@router.get('/cinema/discover')
async def cinema_discover(request: Request):
    authenticate_user(request)
    from shared.modules.cinema_discovery import discovery_shelves
    return {'shelves':await discovery_shelves()}

@router.get('/cinema/title/{imdb_id}')
async def cinema_title(imdb_id:str, request: Request, kind:str='movie'):
    user=authenticate_user(request).decode()
    from shared.modules.cinema_discovery import title_details,ID
    from fastapi import HTTPException
    if not ID.fullmatch(imdb_id) or kind not in {'movie','series'}:raise HTTPException(400,'Invalid title')
    limit='cinema:detail-rate:'+user
    if not redis.exists(f'cinema:detail:v1:{kind}:{imdb_id}'):
        if redis.incr(limit)==1:redis.expire(limit,3600)
        if int(redis.get(limit) or 0)>240:raise HTTPException(429,'Please try again later')
    return {'item':await title_details(imdb_id,kind)}

@router.get('/cinema/search')
async def cinema_search(request: Request, q:str=''):
    user=authenticate_user(request).decode()
    if len(q)>120 or len(q.strip())<2:return {'items':[]}
    from shared.modules.cinema_discovery import search_titles
    limit='cinema:search-rate:'+user
    if redis.incr(limit)==1:redis.expire(limit,3600)
    if int(redis.get(limit) or 0)>240:
        from fastapi import HTTPException
        raise HTTPException(429,'Please try again later')
    return {'items':await search_titles(q.strip())}
