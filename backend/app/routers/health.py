import logging

import httpx
from fastapi import APIRouter

from app import __version__
from app.config import get_settings

logger = logging.getLogger(__name__)
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
    posthog_key_fingerprint = (
        f"{posthog_key[:10]}…{posthog_key[-6:]}"
        if posthog_configured
        and posthog_key.startswith("phc_")
        and len(posthog_key) >= 20
        else None
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
        "posthog_key_fingerprint": posthog_key_fingerprint,
        "posthog_key_length": len(posthog_key) if posthog_configured else 0,
        "rag_via": rag_via,
        "use_mock_llm": use_mock,
    }


@router.get("/health/posthog")
async def health_posthog():
    """
    Live probe: send a synthetic lead_captured from this Railway process.
    Use to verify outbound PostHog without Railway CLI log access.
    """
    settings = get_settings()
    key = (settings.posthog_key or "").strip()
    key_suffix = key[-6:] if len(key) >= 6 else None
    key_fingerprint = (
        f"{key[:10]}…{key[-6:]}" if key.startswith("phc_") and len(key) >= 20 else None
    )
    if not key or settings._is_placeholder(key):
        return {
            "status": "error",
            "posthog_configured": False,
            "key_suffix": None,
            "key_fingerprint": None,
            "detail": "POSTHOG_KEY missing or placeholder on this process",
        }

    import time
    import uuid

    sid = f"health-probe-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    payload = {
        "api_key": key,
        "event": "lead_captured",
        "distinct_id": sid,
        "properties": {
            "session_id": sid,
            "contact_method": "email",
            "diagnosis_category": "health_probe",
            "locale": "en",
            "source": "railway_health_posthog_probe",
            "$lib": "qt-drive-innovations-api",
            "$lib_version": __version__,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                "https://us.i.posthog.com/capture/",
                json=payload,
            )
        body = (resp.text or "")[:200]
        logger.warning(
            "PostHog health probe session=%s http_status=%s key_fingerprint=%s body=%s",
            sid,
            resp.status_code,
            key_fingerprint,
            body,
        )
        return {
            "status": "ok" if resp.status_code < 300 else "error",
            "posthog_configured": True,
            "key_suffix": key_suffix,
            "key_fingerprint": key_fingerprint,
            "key_length": len(key),
            "http_status": resp.status_code,
            "response_body": body,
            "probe_session_id": sid,
            "event": "lead_captured",
            "source": "railway_health_posthog_probe",
            "note": (
                "PostHog often returns HTTP 200 even for invalid keys. "
                "Visibility in Live Events is the real proof."
            ),
        }
    except Exception as exc:
        logger.warning(
            "PostHog health probe EXCEPTION key_fingerprint=%s err=%s",
            key_fingerprint,
            exc,
            exc_info=True,
        )
        return {
            "status": "error",
            "posthog_configured": True,
            "key_suffix": key_suffix,
            "key_fingerprint": key_fingerprint,
            "key_length": len(key),
            "http_status": None,
            "response_body": str(exc)[:200],
            "probe_session_id": None,
            "detail": "exception calling PostHog from Railway",
        }
