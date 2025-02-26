from fastapi import APIRouter, Request, HTTPException
from ..auth.common import authenticate_user
from shared.torrentsearch.search import TorrentSearch

router = APIRouter()
torrent_search = TorrentSearch()

@router.post("/search")
async def search_torrent(query: str, request: Request):
    # Authenticate user
    user_id = authenticate_user(request.cookies.get("session_token"))
    
    try:
        results = torrent_search.search(query)
        if not results:
            return {"data": []}
            
        return {"data": results}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search/get-magnet")
async def search_torrent(data: dict, request: Request):
    # Authenticate user
    user_id = authenticate_user(request.cookies.get("session_token"))
    magnet = torrent_search.get_magnet(data.get("data", {}))
    return {"magnet": magnet}