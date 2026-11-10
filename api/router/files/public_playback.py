"""Public-link playback capabilities: exactly one active shared file per key."""
import hashlib
import mimetypes
import os
import secrets
from pathlib import Path
from urllib.parse import quote
from datetime import datetime
import httpx
from fastapi import APIRouter,HTTPException,Request
from fastapi.responses import FileResponse,Response
from pydantic import BaseModel,constr
from shared.factory import db,redis
from shared.modules.media_filename import file_presentation
from shared.modules.preview_sprites import fingerprint
from .playback import media_path,check_origin,CONTROL,Lease

router=APIRouter(prefix='/public-playback')
VIDEO_EXTENSIONS={'.mp4','.mkv','.webm','.avi','.mov','.m4v','.ts','.m2ts'}

async def public_media(key):
    if not key or len(key)>1024:raise HTTPException(404,'Public URL not found')
    doc=await db.public_urls.find_one({'$or':[{'title':key},{'path_hash':key}],'active':True},{'path':1})
    if not doc:raise HTTPException(404,'Public URL not found')
    file=media_path(doc['path'])
    if file.suffix.lower() not in VIDEO_EXTENSIONS:raise HTTPException(415,'This shared file is not a supported video')
    return file

def public_owner(key):return 'public:'+hashlib.sha256(key.encode()).hexdigest()
def prefix(key):return '/api/files/public-playback/'+quote(key,safe='')
def sidecar(file,name):
    if not name or Path(name).name!=name or '/' in name or '\\' in name:raise HTTPException(404,'Subtitle not found')
    candidate=(file.parent/name).resolve()
    if candidate.parent!=file.parent or candidate.suffix.lower() not in {'.vtt','.srt'} or not (candidate.stem==file.stem or candidate.stem.startswith(file.stem+'.')) or not candidate.is_file() or candidate.stat().st_size>2*1024*1024:
        raise HTTPException(404,'Subtitle not found')
    return candidate

@router.get('/{key}/info')
async def info(key:str):
    file=await public_media(key);redis.setex("media-playback-active",45,1);subtitles=[]
    for entry in file.parent.iterdir():
        if len(subtitles)>=32:break
        if entry.suffix.lower() not in {'.vtt','.srt'}:continue
        try:candidate=sidecar(file,entry.name)
        except HTTPException:continue
        language=entry.stem.rsplit('.',1)[-1].lower()
        subtitles.append({'name':entry.name,'path':'public-subtitle:'+entry.name,'language':language if 2<=len(language)<=3 else 'und'})
    url='/api/files/public/'+quote(key,safe='')
    return {'name':file.name,**file_presentation(file),'size':file.stat().st_size,'type':mimetypes.guess_type(file.name)[0] or 'application/octet-stream',
            'versions':[{'quality':'original','path':'public:'+key,'name':file.name,'url':url,'size':file.stat().st_size}], 'subtitles':subtitles,'direct':os.getenv('WEBRTC_ENABLED','1')=='1'}

@router.get('/{key}/subtitle')
async def subtitle(key:str,name:str):
    return FileResponse(sidecar(await public_media(key),name),media_type='text/plain',headers={'Cache-Control':'no-store'})

class PublicOffer(BaseModel):
    sdp:constr(max_length=32768)

@router.post('/{key}/offer')
async def offer(key:str,body:PublicOffer,request:Request):
    check_origin(request);file=await public_media(key)
    if os.getenv('WEBRTC_ENABLED','1')!='1':raise HTTPException(503,'Direct playback unavailable')
    owner=public_owner(key);rate='public-playback-rate:'+owner
    count=redis.incr(rate)
    if count==1:redis.expire(rate,60)
    if count>12:raise HTTPException(429,'Too many connection attempts')
    peer=secrets.token_hex(32)
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            result=await client.post(CONTROL+'/offer',json={'id':peer,'path':str(file),'offer':{'type':'offer','sdp':body.sdp}})
        if result.status_code!=200:raise HTTPException(503,'Direct playback unavailable')
        redis.setex('public-playback-peer:'+peer,65,owner)
        redis.setex('media-playback-active',45,1)
        return {**result.json(),'id':peer}
    except httpx.HTTPError:raise HTTPException(503,'Direct playback unavailable')

@router.post('/{key}/lease')
async def lease(key:str,body:Lease,request:Request):
    check_origin(request)
    if not body.close:await public_media(key)
    saved=redis.get('public-playback-peer:'+body.id)
    if not saved or saved.decode()!=public_owner(key):raise HTTPException(404,'Connection ended')
    try:
        async with httpx.AsyncClient(timeout=3) as client:result=await client.post(CONTROL+'/lease',json=body.dict())
        if result.status_code!=204:raise HTTPException(404,'Connection ended')
    except httpx.HTTPError:raise HTTPException(503,'Connection unavailable')
    if not body.close:redis.setex('media-playback-active',45,1)
    if body.close:redis.delete('public-playback-peer:'+body.id)
    else:redis.expire('public-playback-peer:'+body.id,65)
    return {'ok':True}

@router.get('/{key}/preview')
async def preview(key:str):
    file=await public_media(key)
    doc=await db.media_previews.find_one({'_id':fingerprint(file)},{'data':0,'accessed_at':0})
    if not doc:return {'status':'unavailable'}
    return {'status':'ready',**{field:value for field,value in doc.items() if field!='_id'},'image':prefix(key)+'/preview-image?v='+fingerprint(file)[:16]}

@router.get('/{key}/preview-image')
async def preview_image(key:str):
    file=await public_media(key);identity=fingerprint(file)
    doc=await db.media_previews.find_one({'_id':identity},{'data':1})
    if not doc:raise HTTPException(404,'Preview not ready')
    await db.media_previews.update_one({'_id':identity},{'$set':{'accessed_at':datetime.utcnow()}})
    return Response(bytes(doc['data']),media_type='image/png',headers={'Cache-Control':'private, no-store'})
