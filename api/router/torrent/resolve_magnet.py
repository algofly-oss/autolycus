import asyncio
import json

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, constr

from shared.factory import jackett, redis
from shared.modules.search_magnets import fetch_magnet
from ..auth.common import authenticate_user

router = APIRouter()
slots = asyncio.Semaphore(4)


class ResolveMagnet(BaseModel):
    token: constr(regex=r"^[A-Za-z0-9_-]{20,64}$")


@router.post('/resolve-magnet')
async def resolve_magnet(payload: ResolveMagnet, request: Request):
    user_id = authenticate_user(request).decode()
    key = 'search_magnet/' + payload.token
    raw = redis.get(key)
    if not raw:
        raise HTTPException(404, 'This result expired. Run the search again.')
    reference = json.loads(raw)
    if reference.get('user_id') != user_id:
        raise HTTPException(404, 'Search result not found.')
    if reference.get('magnet'):
        return {'magnet': reference['magnet']}
    try:
        async with slots:
            magnet = await fetch_magnet(jackett.base_url, jackett.apikey, reference['path'], reference['indexer'])
    except httpx.TimeoutException:
        raise HTTPException(504, 'The source took too long to retrieve the magnet. Try again or open its page.')
    except httpx.HTTPError:
        raise HTTPException(502, 'The indexer could not retrieve this torrent. Try again or open its page.')
    except ValueError as error:
        raise HTTPException(422, str(error))
    reference['magnet'] = magnet
    redis.set(key, json.dumps(reference), ex=3600)
    return {'magnet': magnet}
