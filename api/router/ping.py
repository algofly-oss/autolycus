from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
async def ping():
    return {
        "msg": "pong",
    }
