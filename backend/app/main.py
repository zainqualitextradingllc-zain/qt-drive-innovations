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

# CORS: env list (CORS_ORIGINS) + known production frontends + any *.vercel.app
# preview. Missing the production alias caused browser fetch failures while
# health checks still looked fine (no Origin header on curl).
_DEFAULT_FRONTEND_ORIGINS = [
    "http://localhost:3000",
    "https://qt-drive-innovations.vercel.app",
    "https://qt-drive-innovations-4cgp7jwx7.vercel.app",
]
_cors_origins = list(
    dict.fromkeys(
        (settings.cors_origin_list or []) + _DEFAULT_FRONTEND_ORIGINS
    )
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    # Vercel production alias + git/preview deployments
    allow_origin_regex=r"https://qt-drive-innovations(-[a-z0-9-]+)?\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(chat_router)
# leads_router intentionally omitted until app/routers/leads.py is finished
# and committed with a matching export in app/routers/__init__.py


@app.get("/")
async def root():
    return {
        "name": "QT Drive Innovations API",
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
    }
