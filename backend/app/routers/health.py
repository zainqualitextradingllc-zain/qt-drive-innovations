from fastapi import APIRouter

from app import __version__
from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    settings = get_settings()
    return {
        "status": "ok",
        "service": "qt-drive-innovations-api",
        "version": __version__,
        "llm_provider": settings.llm_provider,
        "openai_configured": settings.openai_configured,
        "gemini_configured": settings.gemini_configured,
        "supabase_configured": settings.supabase_configured,
        "use_mock_llm": settings.use_mock_llm
        or not (
            settings.openai_configured
            if settings.llm_provider == "openai"
            else settings.gemini_configured
        ),
    }
