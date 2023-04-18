from fastapi import APIRouter
from .add import router as add_router
from .get import router as get_router


router = APIRouter(
    prefix="/api/torrent",
    tags=["Torrent Management"],
)

router.include_router(add_router)
router.include_router(get_router)
