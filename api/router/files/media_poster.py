from fastapi import APIRouter, HTTPException, Request, Response

from shared.factory import db
from shared.modules.media_metadata import get_poster_document
from ..auth.common import authenticate_user

router = APIRouter()


@router.get("/media-poster/{metadata_id}")
async def media_poster(metadata_id: str, request: Request):
    user_id = authenticate_user(request).decode("utf-8")
    document = await get_poster_document(db, user_id, metadata_id)
    poster_bytes = document.get("poster_bytes") if document else None
    if not poster_bytes:
        raise HTTPException(status_code=404, detail="Poster not found")

    return Response(
        content=poster_bytes,
        media_type=document.get("poster_mime") or "image/jpeg",
        headers={"Cache-Control": "private, max-age=86400"},
    )
