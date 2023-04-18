from fastapi import APIRouter, Request, Response, HTTPException
from shared.factory import db
from bson import ObjectId
from .common import authenticate_user

router = APIRouter()


@router.get("/me")
async def account_info(request: Request, response: Response):
    # Check if user is logged in
    user_id = authenticate_user(request.cookies.get("session_token"))

    user = await db.users.find_one({"_id": ObjectId(user_id.decode("utf-8"))})

    if not user:
        raise HTTPException(status_code=400, detail="User not logged in")

    return {
        "name": user["name"],
        "username": user["username"],
        "role": user["role"],
        "created_at": user["created_at"],
    }
