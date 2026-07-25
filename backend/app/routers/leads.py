"""Lead capture — PII in Supabase only; funnel signal to PostHog (no contact value)."""

from __future__ import annotations

import logging
import re

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from app import __version__
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/leads", tags=["leads"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class LeadPayload(BaseModel):
    session_id: str
    contact_method: str
    diagnosis_category: str
    locale: str
    contact_value: str

    @field_validator("session_id", "contact_value", "diagnosis_category", "locale")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v or not str(v).strip():
            raise ValueError("must not be empty")
        return str(v).strip()

    @field_validator("contact_method")
    @classmethod
    def valid_method(cls, v: str) -> str:
        if v not in ("email", "line"):
            raise ValueError("contact_method must be 'email' or 'line'")
        return v

    @field_validator("locale")
    @classmethod
    def valid_locale(cls, v: str) -> str:
        if v not in ("en", "ja"):
            raise ValueError("locale must be 'en' or 'ja'")
        return v


async def fire_lead_captured(
    session_id: str,
    contact_method: str,
    diagnosis_category: str,
    locale: str,
) -> dict:
    """
    Send lead_captured to PostHog (no PII).
    Returns a small diagnostic dict (no full key) for API/logs.
    """
    settings = get_settings()
    # Strip quotes — Railway env UI sometimes saves POSTHOG_KEY="phc_..."
    key = (settings.posthog_key or "").strip().strip('"').strip("'")
    key_suffix = key[-6:] if len(key) >= 6 else None
    # e.g. phc_w49d4Y…fcMjMH — enough to match Vercel without exposing the full token
    key_fingerprint = (
        f"{key[:10]}…{key[-6:]}" if key.startswith("phc_") and len(key) >= 20 else None
    )

    if not key or settings._is_placeholder(key):
        # WARNING so it always shows in Railway default log level
        logger.warning(
            "PostHog lead_captured SKIPPED session=%s reason=key_missing_or_placeholder",
            session_id,
        )
        return {
            "attempted": False,
            "ok": False,
            "reason": "key_missing_or_placeholder",
            "key_suffix": None,
            "key_fingerprint": None,
            "key_length": len(key) if key else 0,
            "http_status": None,
            "response_body": None,
        }

    payload = {
        "api_key": key,
        "event": "lead_captured",
        "distinct_id": session_id,
        "properties": {
            "session_id": session_id,
            "contact_method": contact_method,
            "diagnosis_category": diagnosis_category,
            "locale": locale,
            "source": "railway_leads_router",
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
            body_snip = (resp.text or "")[:200]
            ok = resp.status_code < 300
            # Always WARNING so Railway surfaces the line without raising log level
            logger.warning(
                "PostHog lead_captured result session=%s ok=%s http_status=%s "
                "key_fingerprint=%s key_len=%s body=%s",
                session_id,
                ok,
                resp.status_code,
                key_fingerprint,
                len(key),
                body_snip,
            )
            return {
                "attempted": True,
                "ok": ok,
                "reason": None if ok else "http_error",
                "key_suffix": key_suffix,
                "key_fingerprint": key_fingerprint,
                "key_length": len(key),
                "http_status": resp.status_code,
                "response_body": body_snip,
                # Note: PostHog often returns 200 Ok even for bad keys — not proof of ingestion
                "posthog_status_note": (
                    "HTTP 200 Ok from capture does not guarantee the event is visible "
                    "in your project; confirm key_fingerprint matches Vercel NEXT_PUBLIC_POSTHOG_KEY"
                ),
            }
    except Exception as exc:
        logger.warning(
            "PostHog lead_captured EXCEPTION session=%s key_fingerprint=%s err=%s",
            session_id,
            key_fingerprint,
            exc,
            exc_info=True,
        )
        return {
            "attempted": True,
            "ok": False,
            "reason": "exception",
            "key_suffix": key_suffix,
            "key_fingerprint": key_fingerprint,
            "key_length": len(key),
            "http_status": None,
            "response_body": str(exc)[:200],
        }


def _save_lead_row(payload: LeadPayload) -> bool:
    """Persist contact PII. Prefer DATABASE_URL (psycopg); fall back to Supabase client."""
    settings = get_settings()
    row = {
        "session_id": payload.session_id,
        "contact_method": payload.contact_method,
        "contact_value": payload.contact_value,
        "diagnosis_category": payload.diagnosis_category,
        "locale": payload.locale,
    }

    # 1) Direct Postgres (most reliable when pooler/service role JWT is messy)
    if settings.database_configured:
        try:
            import psycopg

            with psycopg.connect(settings.database_url, connect_timeout=15) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        insert into public.diagnostic_leads (
                          session_id, contact_method, contact_value,
                          diagnosis_category, locale
                        ) values (%(session_id)s, %(contact_method)s, %(contact_value)s,
                                  %(diagnosis_category)s, %(locale)s)
                        """,
                        row,
                    )
                conn.commit()
            return True
        except Exception:
            logger.exception(
                "Failed to save lead via DATABASE_URL for session %s",
                payload.session_id,
            )

    # 2) Supabase REST client
    if settings.supabase_configured:
        try:
            from supabase import create_client

            client = create_client(
                settings.supabase_url, settings.supabase_service_role_key
            )
            client.table("diagnostic_leads").insert(row).execute()
            return True
        except Exception:
            logger.exception(
                "Failed to save lead via Supabase client for session %s",
                payload.session_id,
            )
            return False

    logger.warning(
        "No database configured for leads; funnel signal only (session %s)",
        payload.session_id,
    )
    return False


@router.post("/capture")
async def capture_lead(payload: LeadPayload):
    if payload.contact_method == "email" and not _EMAIL_RE.match(payload.contact_value):
        raise HTTPException(status_code=422, detail="invalid email format")

    # 1. PII source of truth (Postgres / Supabase when configured)
    saved = _save_lead_row(payload)

    # 2. Funnel signal only (no contact_value).
    # Awaited (not BackgroundTasks) so Railway workers cannot drop the PostHog
    # call after the HTTP response is already sent.
    posthog = await fire_lead_captured(
        payload.session_id,
        payload.contact_method,
        payload.diagnosis_category,
        payload.locale,
    )

    # posthog diagnostic is safe (suffix only, no full key / no PII)
    return {
        "status": "captured",
        "lead_saved": saved,
        "posthog": posthog,
    }
