from celery import Celery
from celery.result import AsyncResult
from shared.env import REDIS_HOST, REDIS_PASSWORD, REDIS_PORT

redis_url = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0"
app = Celery(
    "tasks",
    broker=redis_url,
    backend=redis_url,
    include=["tasks.transcode_video", "tasks.download_from_url"],
)
