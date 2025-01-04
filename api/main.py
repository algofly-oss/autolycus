from fastapi import FastAPI, WebSocket
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from router import ping, torrent, auth, files
# from sockets import sio_app

API_ROOT = "/api"
app = FastAPI(
    title="Autolycus API",
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
    version="0.1.0",
    docs_url=f"{API_ROOT}/docs",
    openapi_url=f"{API_ROOT}/openapi.json",
)

# app.mount('/socket', app=sio_app)

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
