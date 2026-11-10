from bson import ObjectId
from fastapi import APIRouter,Request
from pydantic import BaseModel,constr
from shared.factory import db
from shared.modules.opensubtitles_client import credentials,encrypt
from .common import authenticate_user
router=APIRouter()
class Connection(BaseModel):
    api_key:constr(max_length=500)=''
    username:constr(max_length=200)=''
    password:constr(max_length=500)=''

@router.get('/opensubtitles')
async def status(request:Request):
    user=authenticate_user(request).decode();value=await credentials(user)
    return {'configured':bool(value.get('api_key')),'username':value.get('username',''),'has_password':bool(value.get('password'))}

@router.put('/opensubtitles')
async def save(body:Connection,request:Request):
    from ..files.playback import check_origin
    user=authenticate_user(request).decode();check_origin(request);old=await credentials(user)
    value={'api_key':body.api_key.strip() or old.get('api_key',''),'username':body.username.strip(),'password':body.password or old.get('password','')}
    await db.users.update_one({'_id':ObjectId(user)},{'$set':{'opensubtitles_connection':encrypt(value)}})
    return {'configured':bool(value['api_key'])}
