"""Per-profile alternate soundtrack choices. Media bytes remain client processed."""
from fastapi import APIRouter,Request,HTTPException
from pydantic import BaseModel,constr,confloat,conint
from shared.factory import db
from shared.modules.media_profiles import profile_id
from ..auth.common import authenticate_user
from .online_subtitles import owned_path
from .playback import check_origin
from .watch_progress import canonical_path

router=APIRouter(prefix='/playback')
class AudioChoice(BaseModel):
    path:constr(max_length=4096)
    donor:constr(max_length=4096)=''
    track_id:conint(ge=0)=0
    delay:confloat(ge=-3600,le=3600,allow_inf_nan=False)=0
    rate:confloat(ge=.5,le=2,allow_inf_nan=False)=1

@router.get('/alternate-audio')
async def get(path:str,request:Request):
    user=authenticate_user(request).decode();profile=await profile_id(request,user)
    path=canonical_path(str(owned_path(path,user)))
    doc=await db.alternate_audio.find_one({'_id':f'{user}:{profile}:{path}'},{'_id':0})
    return {'selection':doc}

@router.put('/alternate-audio')
async def save(body:AudioChoice,request:Request):
    user=authenticate_user(request).decode();profile=await profile_id(request,user);check_origin(request)
    path=canonical_path(str(owned_path(body.path,user)))
    if body.donor:
        donor=owned_path(body.donor,user)
        if donor.suffix.lower() not in {'.mp4','.mkv','.webm','.avi','.m4v','.mov','.ts','.m2ts','.mp3','.aac','.m4a','.flac','.ogg','.wav'}:raise HTTPException(400,'Choose a media file')
    doc=body.dict();doc['path']=path
    await db.alternate_audio.update_one({'_id':f'{user}:{profile}:{path}'},{'$set':doc},upsert=True)
    return {'selection':doc}
