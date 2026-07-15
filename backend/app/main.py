from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import get_settings
from app.routers import chat_router, health_router

settings = get_settings()

app = FastAPI(
    title="QT Drive Innovations API",
    description=(
        "Orchestration layer for the QT Drive Innovations diagnostic assistant "
        "(Skill #1 — car diagnostics). Qualitex Trading LLC."
    ),
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(chat_router)


@app.get("/")
async def root():
    return {
        "name": "QT Drive Innovations API",
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
    }
