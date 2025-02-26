from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from shared.factory import db, redis
from ..auth.common import authenticate_user
from bson import ObjectId
from ..files.delete import delete_dir
import asyncio
from shared.sockets import emit
from .download_status import get_download_status

router = APIRouter()


class DeleteTorrentRequest(BaseModel):
    info_hash: str


@router.post("/delete")
async def delete_torrent(request: DeleteTorrentRequest, request_obj: Request):
    user_id = authenticate_user(request_obj.cookies.get("session_token")).decode(
        "utf-8"
    )
    torrent = await db.torrents.find_one(
        {"info_hash": request.info_hash, "user_id": ObjectId(user_id)},
        {
            "_id": True,
            "info_hash": True,
            "is_finished": True,
            "is_paused": True,
            "save_dir": True,
        },
    )

    if torrent:
        if not torrent["is_finished"]:
            db.torrents.update_one(
                {"_id": torrent["_id"]}, {"$set": {"is_paused": True}}
            )
            redis.set(f"{user_id}/{torrent['info_hash']}/stop", 1)

            # Check the status in the database every 1 second
            while True:
                updated_torrent = await db.torrents.find_one(
                    {"_id": torrent["_id"]}, {"is_paused": True}
                )
                if updated_torrent["is_paused"]:
                    break
                await asyncio.sleep(1)

        # Delete the folder stored at save_dir
        delete_dir(torrent["save_dir"])

        db.torrents.delete_one({"_id": torrent["_id"]})

        emit(
            f"/stc/torrent-added-or-removed",
            {"action": "removed", "info_hash": request.info_hash},
            user_id,
        )
        # emit(f"/stc/download_status", await get_download_status(user_id), user_id)
        return {"message": "Torrent and associated files deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Torrent not found")
