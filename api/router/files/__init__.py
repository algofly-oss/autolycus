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
