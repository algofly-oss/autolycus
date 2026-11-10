import json
from pathlib import Path
from fastapi import APIRouter,Request,HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel,constr,conint
from shared.factory import db,redis
from shared.modules import opensubtitles_client as provider
from shared.modules.media_filename import media_filename
from shared.modules.media_profiles import profile_id
from ..auth.common import authenticate_user
from .playback import media_path,check_origin,quality_versions
from .watch_progress import canonical_path

router=APIRouter(prefix='/playback')
def owned_path(path,user):
    file=media_path(path)
    import os
    root=(Path(os.getenv('DOWNLOAD_PATH','/downloads'))/user).resolve()
    if root not in file.parents:raise HTTPException(403,'Access denied')
    return file

class SubtitleSearch(BaseModel):
    path:constr(max_length=4096)
    language:constr(regex=r'^[a-z]{2,3}$')='en'
    query:constr(max_length=200)=''
class SubtitleSelection(BaseModel):
    path:constr(max_length=4096)
    subtitle:constr(max_length=4096)=''
    language:constr(regex=r'^[a-z]{2,3}$')='en'
    name:constr(max_length=300)=''

@router.post('/opensubtitles/search')
async def search(body:SubtitleSearch,request:Request):
    user=authenticate_user(request).decode();check_origin(request)
    file=media_path(quality_versions(owned_path(body.path,user))[0]['path']);identity=media_filename(file)
    import asyncio
    fingerprint=await asyncio.to_thread(provider.movie_hash,file)
    params={'languages':body.language,'query':body.query.strip() or identity['title']}
    if fingerprint:params['moviehash']=fingerprint
    if identity.get('season') is not None:params['season_number']=identity['season']
    if identity.get('episode') is not None:params['episode_number']=identity['episode'] if isinstance(identity['episode'],int) else identity['episode'][0]
    if identity.get('year'):params['year']=identity['year']
    result=await provider.call(user,'GET','/subtitles',params=dict(sorted(params.items())))
    rows=[]
    for item in result.get('data',[])[:20]:
        attrs=item.get('attributes',{});hash_match=bool(attrs.get('moviehash_match'))
        for entry in attrs.get('files',[])[:3]:
            file_id=entry.get('file_id')
            if not isinstance(file_id,int):continue
            row={'id':file_id,'language':attrs.get('language',body.language),'name':attrs.get('release') or entry.get('file_name') or 'Subtitles','hash_match':hash_match,'hearing_impaired':bool(attrs.get('hearing_impaired')),'downloads':attrs.get('download_count',0)}
            redis.setex(f'subtitle-choice:{user}:{file_id}',3600,canonical_path(body.path));rows.append(row)
    rows.sort(key=lambda row:(not row['hash_match'],-row['downloads']))
    return {'results':rows[:30]}

@router.get('/subtitle-selection')
async def selection(path:str,request:Request):
    user=authenticate_user(request).decode();selected=await profile_id(request,user)
    path=canonical_path(str(owned_path(path,user)))
    doc=await db.subtitle_selections.find_one({'_id':f'{user}:{selected}:{canonical_path(path)}'},{'_id':0})
    return {'selection':doc}

@router.put('/subtitle-selection')
async def save_selection(body:SubtitleSelection,request:Request):
    user=authenticate_user(request).decode();selected=await profile_id(request,user);check_origin(request)
    path=canonical_path(str(owned_path(body.path,user)))
    if body.subtitle.startswith('os:'):
        try:file_id=int(body.subtitle[3:])
        except ValueError:raise HTTPException(400,'Invalid subtitle')
        allowed=redis.get(f'subtitle-choice:{user}:{file_id}')
        existing=await db.subtitle_selections.find_one({'_id':f'{user}:{selected}:{path}','subtitle':body.subtitle})
        if not existing and (not allowed or allowed.decode()!=path):raise HTTPException(403,'Search for this subtitle first')
    doc={'path':path,'subtitle':body.subtitle,'language':body.language,'name':body.name}
    await db.subtitle_selections.update_one({'_id':f'{user}:{selected}:{path}'},{'$set':doc},upsert=True)
    return {'selection':doc}

@router.get('/opensubtitles/file')
async def subtitle_file(path:str,file_id:int,request:Request):
    user=authenticate_user(request).decode();selected=await profile_id(request,user);path=canonical_path(str(owned_path(path,user)))
    allowed=redis.get(f'subtitle-choice:{user}:{file_id}')
    stored=await db.subtitle_selections.find_one({'_id':f'{user}:{selected}:{path}','subtitle':f'os:{file_id}'})
    if not stored and (not allowed or allowed.decode()!=path):raise HTTPException(403,'Subtitle is not selected for this video')
    return PlainTextResponse(await provider.download(user,file_id),headers={'Cache-Control':'private, no-store'})
