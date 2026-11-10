import os
from datetime import datetime
from fastapi import APIRouter,Request,HTTPException
from fastapi.responses import Response
from shared.factory import db,redis
from shared.modules.preview_sprites import fingerprint
from ..auth.common import authenticate_user
from .playback import media_path

router=APIRouter(prefix='/playback')

def _ready(doc,path,key,detail=False,detail_status=None):
    image='/api/files/playback/preview-image?path='+__import__('urllib.parse',fromlist=['quote']).quote(path,safe='')+'&v='+key[:16]
    if detail:image+='&detail=true'
    payload={'status':'ready',**{field:value for field,value in doc.items() if field not in ('_id','source_path')},'image':image}
    if detail_status is not None:payload.update(detail=detail,detail_status=detail_status)
    return payload

@router.get('/preview')
async def preview(path:str,request:Request,detail:bool=False):
    authenticate_user(request);file=media_path(path);key=fingerprint(file,detail)
    doc=await db.media_previews.find_one({'_id':key},{'data':0,'accessed_at':0})
    if doc:return _ready(doc,path,key,detail,'ready' if detail else None)
    coarse_key=fingerprint(file) if detail else key
    coarse=await db.media_previews.find_one({'_id':coarse_key},{'data':0,'accessed_at':0}) if detail else None
    def waiting(status):
        if coarse:return _ready(coarse,path,coarse_key,False,status)
        result={'status':status}
        if detail:result.update(detail=False,detail_status=status)
        return result
    if os.getenv('MEDIA_PREVIEWS_ENABLED','1')=='0' or redis.exists('preview-failed:'+key):return waiting('unavailable')
    parts=file.relative_to(__import__('pathlib').Path(os.getenv('DOWNLOAD_PATH','/downloads')).resolve()).parts
    if len(parts)>=2:
        from bson import ObjectId
        try:
            torrent=await db.torrents.find_one({'user_id':ObjectId(parts[0]),'$or':[{'info_hash':parts[1]},{'url_hash':parts[1]}]},{'is_finished':1})
            if torrent and torrent.get('is_finished') is False:return waiting('pending_download')
        except Exception:pass
    if redis.set('preview-job:'+key,1,nx=True,ex=3600):
        from tasks.media_previews import generate_preview
        if detail:generate_preview.delay(str(file),detail=True)
        else:generate_preview.delay(str(file))
    return waiting('queued')

@router.get('/preview-image')
async def preview_image(path:str,request:Request,detail:bool=False):
    authenticate_user(request);key=fingerprint(media_path(path),detail)
    doc=await db.media_previews.find_one({'_id':key},{'data':1,'content_type':1})
    if not doc:raise HTTPException(404,'Preview not ready')
    await db.media_previews.update_one({'_id':key},{'$set':{'accessed_at':datetime.utcnow()}})
    return Response(bytes(doc['data']),media_type=doc.get('content_type','image/png'),headers={'Cache-Control':'private, max-age=3600','ETag':key})
