from .public_playback import router as public_playback_router
from .alternate_audio import router as alternate_audio_router
from fastapi import APIRouter
from .browse import router as browse_router
from .stream import router as stream_router
from .delete import router as delete_router
from .archive import router as archive_router
from .copy import router as copy_router
from .move import router as move_router
from .rename import router as rename_router
from .status import router as disk_status_router
from .transcode import router as transcode_router
from .public_url import router as public_url_router
from .search import router as search_router
from .media_poster import router as media_poster_router
from .previews import router as previews_router
from .online_subtitles import router as online_subtitles_router
from .watch_progress import router as watch_progress_router
from .playback import router as playback_router

router = APIRouter(prefix="/files", tags=["File Management"])
router.include_router(browse_router)
router.include_router(stream_router)
router.include_router(delete_router)
router.include_router(archive_router)
router.include_router(copy_router)
router.include_router(move_router)
router.include_router(rename_router)
router.include_router(disk_status_router)
router.include_router(transcode_router)
router.include_router(public_url_router)
router.include_router(search_router)
router.include_router(media_poster_router)
router.include_router(playback_router)
router.include_router(previews_router)
router.include_router(watch_progress_router)
router.include_router(online_subtitles_router)

router.include_router(alternate_audio_router)

router.include_router(public_playback_router)

from .cinema import router as cinema_router
router.include_router(cinema_router)

from .online import router as online_router
router.include_router(online_router)
