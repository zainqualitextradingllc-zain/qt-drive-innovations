from fastapi import APIRouter

from app import __version__
from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    settings = get_settings()
    use_mock = settings.use_mock_llm or not (
        settings.openai_configured
        if settings.llm_provider == "openai"
        else settings.gemini_configured
    )
    if settings.database_configured:
        rag_via = "postgres"
    elif settings.supabase_configured:
        rag_via = "supabase"
    else:
        rag_via = "fallback"

    posthog_key = (settings.posthog_key or "").strip()
    posthog_configured = bool(posthog_key) and not settings._is_placeholder(
        posthog_key
    )
    # Last 6 chars only — enough to confirm Railway matches Vercel without leaking the key
    posthog_key_suffix = (
        posthog_key[-6:] if posthog_configured and len(posthog_key) >= 6 else None
    )

    return {
        "status": "ok",
        "service": "qt-drive-innovations-api",
        "version": __version__,
        "llm_provider": settings.llm_provider,
        "openai_configured": settings.openai_configured,
        "gemini_configured": settings.gemini_configured,
        "supabase_configured": settings.supabase_configured,
        "database_configured": settings.database_configured,
        "posthog_configured": posthog_configured,
        "posthog_key_suffix": posthog_key_suffix,
        "rag_via": rag_via,
        "use_mock_llm": use_mock,
    }
