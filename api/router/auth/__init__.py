from fastapi import APIRouter
from .signup import router as signup_router
from .signin import router as signin_router
from .signout import router as signout_router
from .account_info import router as account_info_router
from .delete import router as delete_router

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

router.include_router(account_info_router)
router.include_router(signup_router)
router.include_router(signin_router)
router.include_router(signout_router)
router.include_router(delete_router)
