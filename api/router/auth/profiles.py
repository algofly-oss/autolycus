import uuid
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, constr
from typing import Optional
from shared.factory import db
from shared.modules.media_profiles import ensure_default, AVATARS
from .common import authenticate_user

router=APIRouter()

def visible(doc):
    return {key:doc.get(key) for key in ('id','name','avatar','preferences')}

class ProfileInput(BaseModel):
    name: constr(strip_whitespace=True,min_length=1,max_length=40)
    avatar: str = 'user'

@router.get('/profiles')
async def list_profiles(request:Request):
    user=authenticate_user(request).decode()
    await ensure_default(user)
    docs=await db.media_profiles.find({'user_id':user}).sort([('created_at',1),('name',1)]).to_list(length=None)
    docs.sort(key=lambda doc:doc.get('id')!='default')
    return {'profiles':[visible(doc) for doc in docs]}

@router.post('/profiles')
async def create_profile(body:ProfileInput,request:Request):
    from datetime import datetime
    user=authenticate_user(request).decode()
    if body.avatar not in AVATARS:
        raise HTTPException(400,'Invalid avatar')
    identity=uuid.uuid4().hex
    doc={'_id':f'{user}:{identity}','user_id':user,'id':identity,'name':body.name,'avatar':body.avatar,'preferences':{'video_quality':'auto'},'created_at':datetime.utcnow()}
    await db.media_profiles.insert_one(doc)
    return {'profile':visible(doc)}

@router.patch('/profiles/{identity}')
async def update_profile(identity:str,body:ProfileInput,request:Request):
    user=authenticate_user(request).decode()
    if body.avatar not in AVATARS:
        raise HTTPException(400,'Invalid avatar')
    result=await db.media_profiles.update_one({'_id':f'{user}:{identity}','user_id':user},{'$set':{'name':body.name,'avatar':body.avatar}})
    if not result.matched_count:
        raise HTTPException(404,'Profile not found')
    return {'profile':visible(await db.media_profiles.find_one({'_id':f'{user}:{identity}'}))}
