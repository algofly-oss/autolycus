from fastapi import APIRouter, Response
from shared.env import SIGNUP_DISABLED
from .signup import router as signup_router
from .signin import router as signin_router
from .signout import router as signout_router
from .account_info import router as account_info_router
from .account_update import router as account_update_router
from .ftp import router as ftp_router
from .subtitle_connection import router as subtitle_connection_router
from .profiles import router as profiles_router
from .delete import router as delete_router

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

router.include_router(account_info_router)
router.include_router(profiles_router)
router.include_router(subtitle_connection_router)
router.include_router(account_update_router)
router.include_router(ftp_router)
router.include_router(signup_router)
router.include_router(signin_router)
router.include_router(signout_router)
router.include_router(delete_router)


@router.get("/settings")
async def public_auth_settings(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {"signup_disabled": SIGNUP_DISABLED, "signup_enabled": not SIGNUP_DISABLED}
