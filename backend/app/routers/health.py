import hashlib
import logging

import httpx
from fastapi import APIRouter

from app import __version__
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])

POSTHOG_HOSTS = (
    "https://us.i.posthog.com",
    "https://eu.i.posthog.com",
)


def _posthog_key_meta(posthog_key: str) -> dict:
    """Safe key diagnostics (never return the full secret)."""
    key = (posthog_key or "").strip().strip('"').strip("'")
    configured = bool(key) and not get_settings()._is_placeholder(key)
    if not configured:
        return {
            "posthog_configured": False,
            "posthog_key_suffix": None,
            "posthog_key_fingerprint": None,
            "posthog_key_length": 0,
            "posthog_key_sha12": None,
            "posthog_key_mid8": None,
            "posthog_key_prefix12": None,
        }
    return {
        "posthog_configured": True,
        "posthog_key_suffix": key[-6:] if len(key) >= 6 else None,
        # prefix…suffix is weak (middle can differ). Prefer sha12 for equality checks.
        "posthog_key_fingerprint": (
            f"{key[:10]}…{key[-6:]}"
            if key.startswith("phc_") and len(key) >= 20
            else None
        ),
        "posthog_key_length": len(key),
        "posthog_key_sha12": hashlib.sha256(key.encode("utf-8")).hexdigest()[:12],
        "posthog_key_mid8": key[20:28] if len(key) >= 28 else None,
        "posthog_key_prefix12": key[:12] if len(key) >= 12 else None,
    }


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
    key_meta = _posthog_key_meta(posthog_key)

    return {
        "status": "ok",
        "service": "qt-drive-innovations-api",
        "version": __version__,
        "llm_provider": settings.llm_provider,
        "openai_configured": settings.openai_configured,
        "gemini_configured": settings.gemini_configured,
        "supabase_configured": settings.supabase_configured,
        "database_configured": settings.database_configured,
        **key_meta,
        "rag_via": rag_via,
        "use_mock_llm": use_mock,
    }


@router.get("/health/posthog")
async def health_posthog():
    """
    Live probe: send synthetic lead_captured from this Railway process to US + EU hosts.
    Use to verify outbound PostHog without Railway CLI log access.
    """
    settings = get_settings()
    key = (settings.posthog_key or "").strip().strip('"').strip("'")
    meta = _posthog_key_meta(key)
    if not meta["posthog_configured"]:
        return {
            "status": "error",
            "detail": "POSTHOG_KEY missing or placeholder on this process",
            **meta,
        }

    import time
    import uuid

    base_sid = f"health-probe-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    probes: list[dict] = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        for host in POSTHOG_HOSTS:
            region = "eu" if "eu." in host else "us"
            sid = f"{base_sid}-{region}"
            payload = {
                "api_key": key,
                "event": "lead_captured",
                "distinct_id": sid,
                "properties": {
                    "session_id": sid,
                    "contact_method": "email",
                    "diagnosis_category": "health_probe",
                    "locale": "en",
                    "source": f"railway_health_posthog_probe_{region}",
                    "$lib": "qt-drive-innovations-api",
                    "$lib_version": __version__,
                    "posthog_host": host,
                },
            }
            try:
                resp = await client.post(f"{host}/capture/", json=payload)
                body = (resp.text or "")[:200]
                logger.warning(
                    "PostHog health probe session=%s host=%s http_status=%s sha12=%s body=%s",
                    sid,
                    host,
                    resp.status_code,
                    meta.get("posthog_key_sha12"),
                    body,
                )
                probes.append(
                    {
                        "host": host,
                        "region": region,
                        "probe_session_id": sid,
                        "http_status": resp.status_code,
                        "response_body": body,
                        "ok": resp.status_code < 300,
                    }
                )
            except Exception as exc:
                logger.warning(
                    "PostHog health probe EXCEPTION host=%s sha12=%s err=%s",
                    host,
                    meta.get("posthog_key_sha12"),
                    exc,
                    exc_info=True,
                )
                probes.append(
                    {
                        "host": host,
                        "region": region,
                        "probe_session_id": sid,
                        "http_status": None,
                        "response_body": str(exc)[:200],
                        "ok": False,
                    }
                )

    any_ok = any(p.get("ok") for p in probes)
    return {
        "status": "ok" if any_ok else "error",
        **meta,
        "probes": probes,
        "search_for": [p["probe_session_id"] for p in probes],
        "note": (
            "HTTP 200 Ok is NOT proof of ingestion (invalid keys also return 200). "
            "Compare posthog_key_sha12 to Vercel key hash. "
            "Events must appear in Activity/HogQL to count as success."
        ),
    }
