"""OpenSubtitles REST client; credentials never leave authenticated server code."""
import base64
import hashlib
import json
import os
import struct
from functools import lru_cache
from urllib.parse import urlsplit
from bson import ObjectId
from cryptography.fernet import Fernet
from fastapi import HTTPException
import httpx
from shared.factory import db,redis
from shared.env import API_SECRET_KEY

BASE='https://api.opensubtitles.com/api/v1'

def cipher():return Fernet(base64.urlsafe_b64encode(hashlib.sha256((str(API_SECRET_KEY)+':opensubtitles').encode()).digest()))
def encrypt(value):return cipher().encrypt(json.dumps(value).encode()).decode()
def decrypt(value):
    try:return json.loads(cipher().decrypt(value.encode()))
    except Exception:return {}
async def credentials(user):
    doc=await db.users.find_one({'_id':ObjectId(user)},{'opensubtitles_connection':1})
    result=decrypt((doc or {}).get('opensubtitles_connection',''))
    if not result.get('api_key'):result['api_key']=os.getenv('OPENSUBTITLES_API_KEY','')
    return result

@lru_cache(maxsize=128)
def _movie_hash(path,size,mtime):
    if size<131072:return None
    with open(path,'rb') as stream:
        first=stream.read(65536);stream.seek(-65536,2);last=stream.read(65536)
    value=(size+sum(struct.unpack('<8192Q',first))+sum(struct.unpack('<8192Q',last)))&0xffffffffffffffff
    return f'{value:016x}'
def movie_hash(path):
    stat=path.stat();return _movie_hash(str(path),stat.st_size,stat.st_mtime_ns)

async def call(user,method,endpoint,**kwargs):
    connection=await credentials(user)
    key=connection.get('api_key')
    if not key:raise HTTPException(503,'Connect OpenSubtitles in Settings → Subtitles to search online')
    headers={'Api-Key':key,'User-Agent':os.getenv('OPENSUBTITLES_USER_AGENT','Autolycus v1.0')}
    token_key='opensubtitles-token:'+hashlib.sha256((user+key).encode()).hexdigest()
    async with httpx.AsyncClient(timeout=15,follow_redirects=True) as client:
        if connection.get('username') and connection.get('password'):
            encrypted=redis.get(token_key)
            token=decrypt(encrypted.decode()).get('token') if encrypted else None
            if not token:
                response=await client.post(BASE+'/login',headers=headers,json={'username':connection['username'],'password':connection['password']})
                if response.status_code!=200:raise HTTPException(400,'OpenSubtitles sign-in failed. Check the saved connection.')
                token=response.json().get('token')
                if token:redis.setex(token_key,12*3600,encrypt({'token':token}))
            if token:headers['Authorization']='Bearer '+token
        response=await client.request(method,BASE+endpoint,headers=headers,**kwargs)
        if response.status_code in (406,429):raise HTTPException(429,'OpenSubtitles download or request limit reached. Try again later.')
        if response.status_code in (401,403):
            redis.delete(token_key)
            raise HTTPException(400,'OpenSubtitles rejected the connection. Check the API key and account.')
        if response.status_code>=400:raise HTTPException(502,'OpenSubtitles is unavailable for this request')
        return response.json()

async def download(user,file_id):
    doc=await db.subtitle_cache.find_one({'_id':str(file_id)})
    if doc:
        from datetime import datetime
        await db.subtitle_cache.update_one({'_id':str(file_id)},{'$set':{'accessed_at':datetime.utcnow()}})
        return doc['text']
    result=await call(user,'POST','/download',json={'file_id':file_id,'sub_format':'srt'})
    link=result.get('link','');parsed=urlsplit(link)
    if parsed.scheme!='https' or not (parsed.hostname=='opensubtitles.com' or (parsed.hostname or '').endswith('.opensubtitles.com')):raise HTTPException(502,'Invalid subtitle download response')
    data=bytearray()
    async with httpx.AsyncClient(timeout=20,follow_redirects=False) as client:
        async with client.stream('GET',link) as response:
            if response.status_code!=200:raise HTTPException(502,'Subtitle download unavailable')
            async for part in response.aiter_bytes():
                data.extend(part)
                if len(data)>2*1024*1024:raise HTTPException(413,'Subtitle file exceeds the supported size')
    text=bytes(data).decode('utf-16' if bytes(data[:2]) in (b'\xff\xfe',b'\xfe\xff') else 'utf-8-sig',errors='replace')
    if '-->' not in text:raise HTTPException(422,'OpenSubtitles did not return a supported text subtitle')
    from datetime import datetime
    await db.subtitle_cache.create_index('accessed_at',expireAfterSeconds=30*86400)
    stats=await db.subtitle_cache.aggregate([{'$group':{'_id':None,'bytes':{'$sum':'bytes'}}}]).to_list(1)
    used=stats[0]['bytes'] if stats else 0
    async for old in db.subtitle_cache.find({},{'bytes':1}).sort('accessed_at',1):
        if used+len(data)<=64*1024*1024:break
        await db.subtitle_cache.delete_one({'_id':old['_id']});used-=old.get('bytes',0)
    await db.subtitle_cache.update_one({'_id':str(file_id)},{'$set':{'text':text,'bytes':len(data),'accessed_at':datetime.utcnow()}},upsert=True)
    return text
