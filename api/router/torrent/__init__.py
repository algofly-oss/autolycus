from fastapi import APIRouter
from .add import router as add_router
from .pause import router as pause_router
from .resume import router as resume_router
from .get import router as get_router
from .all import router as all_router
from .delete import router as delete_router
from .search import router as search_router
from .download_status import router as download_status_router


router = APIRouter(
    prefix="/torrent",
    tags=["Torrent Management"],
)

router.include_router(add_router)
router.include_router(pause_router)
router.include_router(resume_router)
router.include_router(get_router)
router.include_router(all_router)
router.include_router(delete_router)
router.include_router(search_router)
router.include_router(download_status_router)