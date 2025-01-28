from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from router import ping, torrent, auth, files
from shared.sockets import sio_app
import celery_worker

API_ROOT = "/api"
app = FastAPI(
    title="Autolycus API",
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
    version="0.1.0",
    docs_url=f"{API_ROOT}/docs",
    openapi_url=f"{API_ROOT}/openapi.json",
)

app.mount(f"/socket.io", app=sio_app)

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


# @app.get("/api/task_status")
# async def task_status(task_id:str):
#     result = celery_worker.AsyncResult(task_id, app=celery_worker.app)
#     if result.ready() and result.successful():
#         return {"state": result.state, "result": result.result}
#     else:
#         return {"state": result.state}

app.include_router(ping.router, prefix=API_ROOT)
app.include_router(auth.router, prefix=API_ROOT)
app.include_router(torrent.router, prefix=API_ROOT)
app.include_router(files.router, prefix=API_ROOT)
