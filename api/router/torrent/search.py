from fastapi import APIRouter, Request, HTTPException
from ..auth.common import authenticate_user
from shared.torrentsearch.search import TorrentSearch

router = APIRouter()

@router.post("/search")
async def search_torrent(query: str, request: Request):
    # Authenticate user
    user_id = authenticate_user(request.cookies.get("session_token"))
    
    try:
        # Initialize torrent search
        torrent_search = TorrentSearch()
        
        # Search for torrents
        results = torrent_search.search(query)

        print("results:", results)
        
        if not results:
            return {"data": []}
            
        return {"data": results}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))