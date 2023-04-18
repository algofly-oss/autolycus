from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from router import ping, torrent, auth


app = FastAPI(
    title="Autolycus API",
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Redirect root to docs
@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse("/docs")


app.include_router(ping.router)
app.include_router(auth.router)
app.include_router(torrent.router)
