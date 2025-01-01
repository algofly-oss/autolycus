from fastapi import APIRouter
from .browse import router as browse_router

router = APIRouter(prefix="/files", tags=["File Management"])
router.include_router(browse_router)
