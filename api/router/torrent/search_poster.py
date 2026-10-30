import re
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, constr

from shared.factory import db
from shared.modules.search_posters import search_poster, touch_poster
from ..auth.common import authenticate_user

router = APIRouter()


class PosterLookup(BaseModel):
    name: constr(strip_whitespace=True, min_length=1, max_length=500)
    kind: Literal['movie', 'tv'] = 'movie'


@router.post('/search-poster')
async def lookup(payload: PosterLookup, request: Request):
    authenticate_user(request)
    return await search_poster(db.search_media_metadata, payload.name, payload.kind)


@router.get('/search-poster/{poster_id}')
async def poster(poster_id: str, request: Request):
    authenticate_user(request)
    if not re.fullmatch(r'[a-f0-9]{64}', poster_id):
        raise HTTPException(404, 'Poster not found')
    doc = await db.search_media_metadata.find_one({'_id': poster_id, 'expires_at': {'$gt': datetime.utcnow()}}, {'poster_bytes': 1, 'poster_mime': 1})
    if not doc or not doc.get('poster_bytes'):
        raise HTTPException(404, 'Poster not found')
    await touch_poster(db.search_media_metadata, poster_id, len(doc['poster_bytes']))
    return Response(content=doc['poster_bytes'], media_type=doc.get('poster_mime') or 'image/jpeg',
                    headers={'Cache-Control': 'private, max-age=86400', 'X-Content-Type-Options': 'nosniff'})
