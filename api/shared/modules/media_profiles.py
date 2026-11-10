"""Account-owned media profiles; active selection belongs to the browser."""
from fastapi import HTTPException
from bson import ObjectId
from shared.factory import db

PROFILE_PREFERENCES = ('home_view_mode','search_view_mode','video_quality','video_subtitles','video_audio_language')
AVATARS = {'user','film','moon','sun','music','star'}

async def profile_id(request, user_id):
    selected=request.headers.get('x-profile-id','default')
    if selected == 'default':
        return selected
    if len(selected)>64 or not await db.media_profiles.find_one({'_id':f'{user_id}:{selected}','user_id':str(user_id)}):
        raise HTTPException(404,'Profile not found')
    return selected

async def ensure_default(user_id):
    user=await db.users.find_one({'_id':ObjectId(str(user_id))})
    if not user:
        raise HTTPException(401,'Account not found')
    preferences={key:value for key,value in (user.get('preferences') or {}).items() if key in PROFILE_PREFERENCES}
    preferences.setdefault('video_quality','auto')
    await db.media_profiles.update_one({'_id':f'{user_id}:default'}, {'$setOnInsert':{'user_id':str(user_id),'id':'default','name':str(user.get('name') or 'My profile')[:40],'avatar':'user','preferences':preferences}},upsert=True)
