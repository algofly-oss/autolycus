"""Account-scoped torrent contents. Temporary leases do not start full downloads."""
import asyncio,time
from fastapi import APIRouter,Request,HTTPException
from pydantic import BaseModel,constr,conint,conlist
from shared.factory import redis
from shared.modules.torrent_preview import previews,PreviewError
from ..auth.common import authenticate_user

router=APIRouter()
class PreviewRequest(BaseModel):
    magnet:constr(min_length=20,max_length=16384)

@router.post('/preview')
async def create_preview(body:PreviewRequest,request:Request):
    user=authenticate_user(request).decode()
    key=f'torrent:preview-rate:{user}:{int(time.time()//3600)}'
    count=redis.incr(key)
    if count==1:redis.expire(key,3600)
    if count>30:raise HTTPException(429,'Too many preview lookups. Please try again later.')
    try:
        token=await asyncio.to_thread(previews.create,user,body.magnet)
        return {'id':token,'status':'metadata','expires_in':900}
    except PreviewError as error:raise HTTPException(409,str(error))

@router.get('/preview/{token}')
async def preview_status(token:str,request:Request):
    user=authenticate_user(request).decode()
    try:return await asyncio.to_thread(previews.status,user,token)
    except PreviewError as error:raise HTTPException(404,str(error))

@router.delete('/preview/{token}')
async def close_preview(token:str,request:Request):
    user=authenticate_user(request).decode()
    try:await asyncio.to_thread(previews.close,user,token)
    except PreviewError as error:raise HTTPException(404,str(error))
    return {'closed':True}

class SelectedFiles(BaseModel):
    indices:conlist(conint(strict=True,ge=0,lt=4000),min_items=1,max_items=4000)

@router.post('/preview/{token}/download')
async def download_selected(token:str,body:SelectedFiles,request:Request):
    from bson import ObjectId
    from bson.binary import Binary
    from datetime import datetime
    import libtorrent as lt
    from shared.factory import db
    from shared.modules.libtorrentx import LibTorrentSession
    from shared.sockets import emit
    from .common import update_to_db
    user=authenticate_user(request).decode()
    try:spec=await asyncio.to_thread(previews.download_spec,user,token,body.indices)
    except PreviewError as error:raise HTTPException(409,str(error))
    key={'user_id':ObjectId(user),'info_hash':spec['info_hash']}
    lock=redis.lock(f'torrent:selected-add:{user}:{spec["info_hash"]}',timeout=20)
    if not lock.acquire(blocking=False):raise HTTPException(409,'This download is already being added.')
    inserted=None
    handle=None
    try:
        if await db.torrents.find_one(key,{'_id':1}):raise HTTPException(409,'This torrent is already in your downloads.')
        metadata=lt.torrent_info(spec['metadata'])
        row={**key,'magnet':spec['magnet'],'selected_files':spec['indices'],'torrent_metadata':Binary(spec['metadata']),'created_at':datetime.now(),'is_paused':False,'is_finished':False,
             'name':metadata.name(),'save_dir':f'/downloads/{user}/{spec["info_hash"]}','ok':True,'download_speed':0,'downloaded_bytes':0,'progress':0,'upload_speed':0,'num_connections':0,'num_peers':0,'num_seeds':0,'num_trackers':0,'queue_position':0,
             'total_bytes':sum(metadata.files().file_size(i) for i in spec['indices'])}
        inserted=await db.torrents.insert_one(row)
        await asyncio.to_thread(previews.handoff,user,token)
        await asyncio.sleep(.1)
        session=LibTorrentSession(redis=redis)
        handle=session.add_torrent(spec['magnet'],f'/downloads/{user}',file_indices=spec['indices'],metadata=metadata)
        redis.delete(f'{user}/{spec["info_hash"]}/stop',f'{user}/{spec["info_hash"]}/copied_from_existing')
        handle.set_callback(lambda props:update_to_db(props,ObjectId(user)),callback_interval=1,user_id=user)
        emit('/stc/torrent-added-or-removed',{'action':'added','info_hash':spec['info_hash']},user)
        return {'message':'Selected files added','info_hash':spec['info_hash'],'selected_files':spec['indices']}
    except HTTPException:raise
    except Exception:
        if handle:
            handle.remove_callback();session._stop(spec["info_hash"])
        if inserted:await db.torrents.delete_one({'_id':inserted.inserted_id})
        raise HTTPException(502,'Could not start this download.')
    finally:
        try:lock.release()
        except Exception:pass

preview_streams=asyncio.Semaphore(4)

@router.get('/preview/{token}/file/{index}/info')
async def preview_file_info(token:str,index:int,request:Request):
    import mimetypes
    user=authenticate_user(request).decode()
    try:file=await asyncio.to_thread(previews.file_info,user,token,index)
    except PreviewError as error:raise HTTPException(404,str(error))
    redis.setex('media-playback-active',45,1)
    url=f'/api/torrent/preview/{token}/file/{index}'
    return {'name':file['name'],'size':file['size'],'type':mimetypes.guess_type(file['name'])[0] or 'application/octet-stream','direct':False,'subtitles':[],'versions':[{'quality':'original','url':url,'name':file['name'],'size':file['size']}]}

@router.get('/preview/{token}/file/{index}')
async def preview_stream(token:str,index:int,request:Request):
    import re,threading,mimetypes
    from starlette.responses import StreamingResponse
    user=authenticate_user(request).decode()
    try:file=await asyncio.to_thread(previews.file_info,user,token,index)
    except PreviewError as error:raise HTTPException(404,str(error))
    size=file['size'];start,end=0,size-1;header=request.headers.get('range')
    if header:
        match=re.fullmatch(r'bytes=(\d*)-(\d*)',header)
        invalid=HTTPException(416,'Range not satisfiable',headers={'Content-Range':f'bytes */{size}'})
        if len(header)>128 or not match or not any(match.groups()):raise invalid
        if match[1]:start=int(match[1]);end=min(int(match[2]),size-1) if match[2] else size-1
        elif int(match[2])>0:start=max(0,size-int(match[2]))
        else:raise invalid
        if start>end or start>=size:raise invalid
    try:await asyncio.wait_for(preview_streams.acquire(),2)
    except asyncio.TimeoutError:raise HTTPException(503,'Preview is busy. Please try again.')
    cancelled=threading.Event()
    try:first=await asyncio.to_thread(previews.read,user,token,index,start,min(256*1024,end-start+1),cancelled)
    except BaseException as error:
        cancelled.set();preview_streams.release()
        if isinstance(error,PreviewError):raise HTTPException(503,str(error))
        raise
    async def chunks():
        position=start
        try:
            redis.setex('media-playback-active',45,1);marked=time.monotonic()
            yield first;position+=len(first)
            while position<=end:
                if await request.is_disconnected():return
                data=await asyncio.to_thread(previews.read,user,token,index,position,min(256*1024,end-position+1),cancelled)
                if time.monotonic()-marked>=15:redis.setex('media-playback-active',45,1);marked=time.monotonic()
                yield data;position+=len(data)
        finally:
            cancelled.set();preview_streams.release()
            try:previews.suspend(user,token)
            except PreviewError:pass
    headers={'Accept-Ranges':'bytes','Content-Length':str(end-start+1),'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'}
    if header:headers['Content-Range']=f'bytes {start}-{end}/{size}'
    return StreamingResponse(chunks(),status_code=206 if header else 200,headers=headers,media_type=mimetypes.guess_type(file['name'])[0] or 'application/octet-stream')

@router.post('/preview/{token}/suspend')
async def suspend_preview(token:str,request:Request):
    user=authenticate_user(request).decode()
    try:await asyncio.to_thread(previews.suspend,user,token)
    except PreviewError as error:raise HTTPException(404,str(error))
    return {'suspended':True}
