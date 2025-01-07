from fastapi import APIRouter
from .browse import router as browse_router
from .stream import router as stream_router
from .delete import router as delete_router
from .archive import router as archive_router

router = APIRouter(prefix="/files", tags=["File Management"])
router.include_router(browse_router)
router.include_router(stream_router)
router.include_router(delete_router)
router.include_router(archive_router)
