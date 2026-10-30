import asyncio

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from router import ping, torrent, auth, files
from shared.factory import db
from shared.modules.file_search_index import schedule_missing_search_index_backfill
from shared.sockets import sio_app
from router.auth.ftp import refresh_ftp_friendly_roots
import celery_worker
from shared.env import SESSION_COOKIE_NAME
from shared.modules.auth_session import resolve_session, set_session_cookie
from shared.modules.storage_usage import refresh_storage_usage

API_ROOT = "/api"
app = FastAPI(
    title="Autolycus API",
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
    version="0.1.0",
    docs_url=f"{API_ROOT}/docs",
    openapi_url=f"{API_ROOT}/openapi.json",
)

app.mount(f"/socket.io", app=sio_app)
ftp_sync_task = None
storage_usage_task = None


async def _storage_usage_loop():
    while True:
        await asyncio.sleep(60)
        try:
            await asyncio.to_thread(refresh_storage_usage)
        except Exception as error:
            print(f"Storage usage refresh failed: {type(error).__name__}")


@app.on_event("startup")
async def startup_storage_usage():
    global storage_usage_task
    await asyncio.to_thread(refresh_storage_usage)
    storage_usage_task = asyncio.create_task(_storage_usage_loop())


@app.on_event("shutdown")
async def shutdown_storage_usage():
    if storage_usage_task:
        storage_usage_task.cancel()


@app.middleware("http")
async def persistent_session(request, call_next):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user_id, renewed = await resolve_session(token)
    request.state.session_user_id = user_id
    response = await call_next(request)
    if request.url.path.startswith("/api/auth"):
        response.headers["Cache-Control"] = "no-store, private"
    # Explicit login/logout/revocation owns its cookie response; never restore
    # a cookie just deleted by the endpoint.
    cookie_prefix = (SESSION_COOKIE_NAME + "=").encode()
    cookie_written = any(name.lower() == b"set-cookie" and value.startswith(cookie_prefix)
                         for name, value in response.raw_headers)
    if renewed and user_id and response.status_code < 400 and not cookie_written:
        set_session_cookie(response, request, token)
    return response


@app.on_event("startup")
async def startup_backfill_search_index():
    schedule_missing_search_index_backfill(db)


async def _ftp_friendly_root_sync_loop():
    while True:
        try:
            await refresh_ftp_friendly_roots()
        except Exception as error:
            print(f"FTP friendly-root sync failed: {error}")
        await asyncio.sleep(10)


@app.on_event("startup")
async def startup_ftp_friendly_root_sync():
    global ftp_sync_task
    ftp_sync_task = asyncio.create_task(_ftp_friendly_root_sync_loop())


@app.on_event("shutdown")
async def shutdown_ftp_friendly_root_sync():
    if ftp_sync_task:
        ftp_sync_task.cancel()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


# Redirect root to docs
@app.get(API_ROOT, include_in_schema=False)
async def root():
    return RedirectResponse(f"{API_ROOT}/docs")


app.include_router(ping.router, prefix=API_ROOT)
app.include_router(auth.router, prefix=API_ROOT)
app.include_router(torrent.router, prefix=API_ROOT)
app.include_router(files.router, prefix=API_ROOT)
