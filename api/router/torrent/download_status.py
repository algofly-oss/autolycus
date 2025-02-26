from fastapi import APIRouter, Request, HTTPException
from shared.factory import db  
from ..auth.common import authenticate_user
from typing import Dict, List
from bson import ObjectId

router = APIRouter()

async def get_download_status(user_id: str) -> Dict[str, int]:
    """
    Calculate active and finished downloads for a given user.
    
    Args:
        user_id (str): The user's ID to fetch downloads for
    
    Returns:
        Dict containing counts of active and finished downloads
    """
    try:
        # Fetch torrents from database
        torrents: List[Dict] = await db.torrents.find({
            "user_id": ObjectId(user_id)
        }).to_list(length=None)
        
        # Initialize counters
        active_count = 0
        finished_count = 0
        
        # Count active and finished downloads
        for torrent in torrents:
            if torrent.get("is_finished", False):
                finished_count += 1
            else:
                active_count += 1
                
        return {
            "active_downloads": active_count,
            "finished_downloads": finished_count,
            "total_downloads": active_count + finished_count
        }
        
    except Exception as e:
        print(f"Error calculating download status: {str(e)}")
        return {
            "active_downloads": 0,
            "finished_downloads": 0,
            "total_downloads": 0
        }


@router.get("/download-status")
async def download_status(request: Request):
    """
    API endpoint to get download status for authenticated user.
    """
    try:
        user_id = authenticate_user(request.cookies.get("session_token")).decode()
        status = await get_download_status(user_id)
        return status
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve download status: {str(e)}"
        )