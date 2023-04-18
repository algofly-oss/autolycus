from fastapi import APIRouter
import requests
import time

router = APIRouter(
    prefix="/api",
)


@router.get("/ping")
async def ping():
    st = time.perf_counter()
    requests.get("https://google.com")

    return {
        "msg": "pong",
        "latency": f"{(time.perf_counter() - st) * 1000:.3f} ms",
    }
