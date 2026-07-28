"""
Phase 4a.0 — diagnosis integrity attestation (SHA-256 + Supabase).

No blockchain, no PII. Fail-safe: callers must catch/log and never block lead flow.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from app import __version__
from app.config import get_settings
from app.models.diagnosis import DiagnosisPayload

logger = logging.getLogger(__name__)

# Fixed model tag for hashed payload (independent of API package version bumps if needed)
MODEL_VERSION = f"qt-drive-diag-{__version__}"


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _parse_cost_range_from_text(estimated_cost: str | None) -> tuple[float | None, float | None]:
    """
    Extract numeric min/max from localized cost strings when cost_min/max
    were not set (LLM often only emits estimated_cost like '200-600 USD').
    """
    if not estimated_cost or not str(estimated_cost).strip():
        return None, None
    text = str(estimated_cost).replace(",", "").replace("，", "")
    # Normalize common range separators: 〜 ~ – — to -
    for sep in ("〜", "~", "–", "—", " to ", " TO "):
        text = text.replace(sep, "-")
    # Find two numbers in order (min then max)
    nums = re.findall(r"\d+(?:\.\d+)?", text)
    if len(nums) >= 2:
        lo, hi = float(nums[0]), float(nums[1])
        if lo > hi:
            lo, hi = hi, lo
        return lo, hi
    if len(nums) == 1:
        v = float(nums[0])
        return v, v
    return None, None


def _vehicle_dict_from_sources(
    diagnosis: DiagnosisPayload,
    vehicle_fallback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Prefer diagnosis.vehicle_context fields; fill gaps from session vehicle.
    Placeholder LLM values (year=0, make='unknown') become null so verify
    page shows "Not specified" instead of "0 unknown unknown".
    Never includes VIN.
    """
    from app.services.vehicle_identity import sanitize_vehicle_fields

    base: dict[str, Any] = {
        "engine": None,
        "make": None,
        "model": None,
        "year": None,
    }
    vc = diagnosis.vehicle_context
    if vc is not None:
        base = sanitize_vehicle_fields(vc.model_dump())

    fb = sanitize_vehicle_fields(vehicle_fallback)
    for key in ("year", "make", "model", "engine"):
        if base.get(key) is None and fb.get(key) is not None:
            base[key] = fb.get(key)
    return base


def build_canonical_payload(
    *,
    diagnosis_id: str,
    session_id: str,
    diagnosis: DiagnosisPayload,
    locale: str,
    model_version: str = MODEL_VERSION,
    timestamp: str | None = None,
    vehicle_fallback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Fixed schema for hashing. Keys will be sorted at serialize time.

    Includes: diagnosis_id, session_id, vehicle, causes[], cost_min, cost_max,
    locale, model_version, timestamp.
    Excludes: email, phone, LINE, name, contact_method, free-text disclaimers.
    Vehicle omits VIN (identifier PII) — year/make/model/engine only.
    """
    causes = [
        {
            "cause": c.cause,
            "confidence": float(c.confidence),
        }
        for c in (diagnosis.diagnosis or [])
    ]

    vehicle = _vehicle_dict_from_sources(diagnosis, vehicle_fallback)

    cost_min = diagnosis.cost_min
    cost_max = diagnosis.cost_max
    if cost_min is not None:
        cost_min = float(cost_min)
    if cost_max is not None:
        cost_max = float(cost_max)
    # Fallback: parse estimated_cost string when structured min/max absent
    if cost_min is None or cost_max is None:
        parsed_lo, parsed_hi = _parse_cost_range_from_text(diagnosis.estimated_cost)
        if cost_min is None:
            cost_min = parsed_lo
        if cost_max is None:
            cost_max = parsed_hi

    return {
        "causes": causes,
        "cost_max": cost_max,
        "cost_min": cost_min,
        "diagnosis_id": diagnosis_id,
        "locale": locale,
        "model_version": model_version,
        "session_id": session_id,
        "timestamp": timestamp or _utc_now_iso(),
        "vehicle": vehicle,
    }


def serialize_canonical(payload: dict[str, Any]) -> str:
    """Deterministic JSON: sorted keys, compact separators, UTF-8 friendly."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(canonical_json_str: str) -> str:
    return hashlib.sha256(canonical_json_str.encode("utf-8")).hexdigest()


def compute_content_hash(payload: dict[str, Any]) -> tuple[str, str]:
    """Returns (canonical_json_string, content_hash_hex)."""
    s = serialize_canonical(payload)
    return s, sha256_hex(s)


def verify_content_hash(canonical: dict[str, Any] | str, expected_hash: str) -> bool:
    if isinstance(canonical, str):
        recomputed = sha256_hex(canonical)
    else:
        _, recomputed = compute_content_hash(canonical)
    return recomputed.lower() == (expected_hash or "").lower()


def _save_via_postgres(
    *,
    diagnosis_id: str,
    session_id: str,
    canonical: dict[str, Any],
    content_hash: str,
) -> bool:
    import psycopg

    settings = get_settings()
    with psycopg.connect(settings.database_url, connect_timeout=15) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into public.diagnostic_attestations (
                  diagnosis_id, session_id, canonical_json, content_hash, anchor_status
                ) values (
                  %s, %s, %s::jsonb, %s, 'hashed'
                )
                on conflict (content_hash) do nothing
                """,
                (
                    diagnosis_id,
                    session_id,
                    json.dumps(canonical, ensure_ascii=False),
                    content_hash,
                ),
            )
        conn.commit()
    return True


def _save_via_supabase(
    *,
    diagnosis_id: str,
    session_id: str,
    canonical: dict[str, Any],
    content_hash: str,
) -> bool:
    from supabase import create_client

    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    client.table("diagnostic_attestations").upsert(
        {
            "diagnosis_id": diagnosis_id,
            "session_id": session_id,
            "canonical_json": canonical,
            "content_hash": content_hash,
            "anchor_status": "hashed",
        },
        on_conflict="content_hash",
    ).execute()
    return True


def create_diagnosis_attestation(
    *,
    session_id: str,
    diagnosis: DiagnosisPayload,
    locale: str,
    vehicle_fallback: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Build canonical JSON, SHA-256, persist. Returns summary or None on failure.
    Never raises to callers that want fail-safe behavior (they may still try/except).

    vehicle_fallback: session vehicle dict (year/make/model/engine) when
    diagnosis.vehicle_context is empty but the chat UI had vehicle context.
    """
    try:
        diagnosis_id = str(uuid.uuid4())
        canonical = build_canonical_payload(
            diagnosis_id=diagnosis_id,
            session_id=session_id,
            diagnosis=diagnosis,
            locale=locale,
            vehicle_fallback=vehicle_fallback,
        )
        canonical_str, content_hash = compute_content_hash(canonical)

        settings = get_settings()
        saved = False
        if settings.database_configured:
            try:
                saved = _save_via_postgres(
                    diagnosis_id=diagnosis_id,
                    session_id=session_id,
                    canonical=canonical,
                    content_hash=content_hash,
                )
            except Exception:
                logger.exception(
                    "attestation postgres save failed session=%s hash=%s",
                    session_id,
                    content_hash[:16],
                )
        if not saved and settings.supabase_configured:
            try:
                saved = _save_via_supabase(
                    diagnosis_id=diagnosis_id,
                    session_id=session_id,
                    canonical=canonical,
                    content_hash=content_hash,
                )
            except Exception:
                logger.exception(
                    "attestation supabase save failed session=%s hash=%s",
                    session_id,
                    content_hash[:16],
                )

        result = {
            "diagnosis_id": diagnosis_id,
            "content_hash": content_hash,
            "canonical_json": canonical,
            "canonical_json_str": canonical_str,
            "persisted": saved,
            "anchor_status": "hashed",
        }

        if not saved:
            logger.warning(
                "attestation not persisted (no DB); session=%s hash=%s",
                session_id,
                content_hash[:16],
            )
        else:
            logger.info(
                "attestation saved session=%s diagnosis_id=%s hash=%s",
                session_id,
                diagnosis_id,
                content_hash[:16],
            )

        # PostHog: diagnosis_attested only (never touches lead_captured). Fail-safe.
        # Always log at WARNING so Railway default logs show fire + response.
        try:
            ph = fire_diagnosis_attested(
                session_id=session_id,
                diagnosis_id=diagnosis_id,
                content_hash=content_hash,
            )
            result["posthog_diagnosis_attested"] = ph
        except Exception:
            logger.warning(
                "diagnosis_attested PostHog fire failed session=%s",
                session_id,
                exc_info=True,
            )

        return result
    except Exception:
        logger.exception("create_diagnosis_attestation failed session=%s", session_id)
        return None


def _resolve_posthog_key() -> str:
    """Same project token as frontend when possible (POSTHOG_KEY or NEXT_PUBLIC_*)."""
    import os

    settings = get_settings()
    candidates = [
        (settings.posthog_key or "").strip().strip('"').strip("'"),
        (os.environ.get("POSTHOG_KEY") or "").strip().strip('"').strip("'"),
        (os.environ.get("NEXT_PUBLIC_POSTHOG_KEY") or "").strip().strip('"').strip("'"),
    ]
    for key in candidates:
        if key and not settings._is_placeholder(key):
            return key
    return ""


def fire_diagnosis_attested(
    *,
    session_id: str,
    diagnosis_id: str,
    content_hash: str,
) -> dict[str, Any]:
    """
    Capture diagnosis_attested to PostHog US host (same as lead_captured / browser).
    Temporary verbose WARNING logs for production debugging.
    """
    import httpx

    from app import __version__

    key = _resolve_posthog_key()
    prefix = (content_hash or "")[:8]
    key_suffix = key[-6:] if len(key) >= 6 else None
    host = "https://us.i.posthog.com/capture/"

    if not key:
        logger.warning(
            "diagnosis_attested SKIPPED session=%s diagnosis_id=%s "
            "reason=no_posthog_key host=%s prefix=%s",
            session_id,
            diagnosis_id,
            host,
            prefix,
        )
        return {
            "attempted": False,
            "ok": False,
            "reason": "no_posthog_key",
            "http_status": None,
            "response_body": None,
            "key_suffix": None,
            "host": host,
            "content_hash_prefix": prefix,
        }

    payload = {
        "api_key": key,
        "event": "diagnosis_attested",
        "distinct_id": session_id,
        "properties": {
            "diagnosis_id": diagnosis_id,
            "content_hash_prefix": prefix,
            "session_id": session_id,
            "$lib": "qt-drive-innovations-api",
            "$lib_version": __version__,
            "source": "attestation_service",
        },
    }

    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(host, json=payload)
        body = (resp.text or "")[:200]
        ok = resp.status_code < 300
        logger.warning(
            "diagnosis_attested RESULT session=%s diagnosis_id=%s ok=%s "
            "http_status=%s key_suffix=%s host=%s prefix=%s body=%s",
            session_id,
            diagnosis_id,
            ok,
            resp.status_code,
            key_suffix,
            host,
            prefix,
            body,
        )
        return {
            "attempted": True,
            "ok": ok,
            "reason": None if ok else "http_error",
            "http_status": resp.status_code,
            "response_body": body,
            "key_suffix": key_suffix,
            "host": host,
            "content_hash_prefix": prefix,
        }
    except Exception as exc:
        logger.warning(
            "diagnosis_attested EXCEPTION session=%s diagnosis_id=%s "
            "key_suffix=%s host=%s err=%s",
            session_id,
            diagnosis_id,
            key_suffix,
            host,
            exc,
            exc_info=True,
        )
        return {
            "attempted": True,
            "ok": False,
            "reason": "exception",
            "http_status": None,
            "response_body": str(exc)[:200],
            "key_suffix": key_suffix,
            "host": host,
            "content_hash_prefix": prefix,
        }


def fetch_attestation_by_hash(content_hash: str) -> dict[str, Any] | None:
    """Load attestation row by content_hash. Returns None if missing."""
    h = (content_hash or "").strip().lower()
    if not h or len(h) < 32:
        return None

    settings = get_settings()
    if settings.database_configured:
        try:
            import psycopg

            with psycopg.connect(settings.database_url, connect_timeout=15) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        select diagnosis_id, session_id, canonical_json, content_hash,
                               created_at, chain_id, tx_hash, anchor_status
                        from public.diagnostic_attestations
                        where lower(content_hash) = %s
                        limit 1
                        """,
                        (h,),
                    )
                    row = cur.fetchone()
                    if not row:
                        return None
                    (
                        diagnosis_id,
                        session_id,
                        canonical_json,
                        content_hash_db,
                        created_at,
                        chain_id,
                        tx_hash,
                        anchor_status,
                    ) = row
                    if isinstance(canonical_json, str):
                        canonical_json = json.loads(canonical_json)
                    return {
                        "diagnosis_id": diagnosis_id,
                        "session_id": session_id,
                        "canonical_json": canonical_json,
                        "content_hash": content_hash_db,
                        "created_at": created_at.isoformat() if created_at else None,
                        "chain_id": chain_id,
                        "tx_hash": tx_hash,
                        "anchor_status": anchor_status,
                    }
        except Exception:
            logger.exception("fetch_attestation postgres failed hash=%s", h[:16])

    if settings.supabase_configured:
        try:
            from supabase import create_client

            client = create_client(
                settings.supabase_url, settings.supabase_service_role_key
            )
            res = (
                client.table("diagnostic_attestations")
                .select(
                    "diagnosis_id,session_id,canonical_json,content_hash,"
                    "created_at,chain_id,tx_hash,anchor_status"
                )
                .eq("content_hash", h)
                .limit(1)
                .execute()
            )
            rows = res.data or []
            if not rows:
                # try case-insensitive via filter if stored mixed
                res = (
                    client.table("diagnostic_attestations")
                    .select(
                        "diagnosis_id,session_id,canonical_json,content_hash,"
                        "created_at,chain_id,tx_hash,anchor_status"
                    )
                    .ilike("content_hash", h)
                    .limit(1)
                    .execute()
                )
                rows = res.data or []
            if not rows:
                return None
            return rows[0]
        except Exception:
            logger.exception("fetch_attestation supabase failed hash=%s", h[:16])

    return None


# Explorer templates for ProofChain™ (Phase 4a.1)
_EXPLORER_TX = {
    "polygon_amoy": "https://amoy.polygonscan.com/tx/{tx}",
    "polygon": "https://polygonscan.com/tx/{tx}",
    "base_sepolia": "https://sepolia.basescan.org/tx/{tx}",
    "base": "https://basescan.org/tx/{tx}",
}


def fetch_merkle_onchain(content_hash: str) -> dict[str, Any] | None:
    """
    QT ProofChain™: load Merkle inclusion + batch tx if this hash was anchored.
    Read-only. Returns None when not yet in any confirmed/submitted batch.
    """
    h = (content_hash or "").strip().lower()
    if not h or len(h) < 32:
        return None

    settings = get_settings()

    def _pack(row: dict[str, Any]) -> dict[str, Any]:
        chain = (row.get("chain_name") or "").lower()
        tx = row.get("tx_hash")
        explorer = None
        if tx and chain in _EXPLORER_TX:
            explorer = _EXPLORER_TX[chain].format(tx=tx)
        return {
            "content_hash": row.get("content_hash"),
            "leaf_hash": row.get("leaf_hash"),
            "proof": row.get("proof") or [],
            "leaf_index": row.get("leaf_index"),
            "batch_id": str(row.get("batch_id")) if row.get("batch_id") else None,
            "merkle_root": row.get("merkle_root"),
            "tx_hash": tx,
            "block_number": row.get("block_number"),
            "chain_name": row.get("chain_name"),
            "chain_id": row.get("chain_id"),
            "contract_address": row.get("contract_address"),
            "anchored_at": row.get("anchored_at") or row.get("created_at"),
            "batch_status": row.get("batch_status") or row.get("status"),
            "explorer_url": explorer,
        }

    if settings.database_configured:
        try:
            import psycopg

            with psycopg.connect(settings.database_url, connect_timeout=15) as conn:
                with conn.cursor() as cur:
                    try:
                        cur.execute(
                            """
                            select content_hash, leaf_hash, proof, leaf_index,
                                   batch_id, merkle_root, tx_hash, block_number,
                                   chain_name, chain_id, contract_address,
                                   anchored_at, batch_status
                            from public.v_attestation_onchain
                            where lower(content_hash) = %s
                            order by anchored_at desc nulls last
                            limit 1
                            """,
                            (h,),
                        )
                    except Exception:
                        cur.execute(
                            """
                            select p.content_hash, p.leaf_hash, p.proof, p.leaf_index,
                                   p.batch_id, b.merkle_root, b.tx_hash, b.block_number,
                                   b.chain_name, b.chain_id, b.contract_address,
                                   b.created_at, b.status
                            from public.attestation_merkle_proofs p
                            join public.anchor_batches b on b.batch_id = p.batch_id
                            where lower(p.content_hash) = %s
                              and b.status in ('submitted', 'confirmed')
                            order by b.created_at desc
                            limit 1
                            """,
                            (h,),
                        )
                    row = cur.fetchone()
                    if not row:
                        return None
                    keys = [
                        "content_hash",
                        "leaf_hash",
                        "proof",
                        "leaf_index",
                        "batch_id",
                        "merkle_root",
                        "tx_hash",
                        "block_number",
                        "chain_name",
                        "chain_id",
                        "contract_address",
                        "anchored_at",
                        "batch_status",
                    ]
                    data = dict(zip(keys, row))
                    if hasattr(data.get("anchored_at"), "isoformat"):
                        data["anchored_at"] = data["anchored_at"].isoformat()
                    if isinstance(data.get("proof"), str):
                        data["proof"] = json.loads(data["proof"])
                    return _pack(data)
        except Exception:
            logger.exception("fetch_merkle_onchain postgres failed hash=%s", h[:16])

    if settings.supabase_configured:
        try:
            from supabase import create_client

            client = create_client(
                settings.supabase_url, settings.supabase_service_role_key
            )
            res = (
                client.table("attestation_merkle_proofs")
                .select(
                    "content_hash,leaf_hash,proof,leaf_index,batch_id,"
                    "anchor_batches(merkle_root,tx_hash,block_number,chain_name,"
                    "chain_id,contract_address,created_at,status)"
                )
                .eq("content_hash", h)
                .limit(5)
                .execute()
            )
            for r in res.data or []:
                b = r.get("anchor_batches") or {}
                if b.get("status") not in ("submitted", "confirmed"):
                    continue
                return _pack(
                    {
                        "content_hash": r.get("content_hash"),
                        "leaf_hash": r.get("leaf_hash"),
                        "proof": r.get("proof"),
                        "leaf_index": r.get("leaf_index"),
                        "batch_id": r.get("batch_id"),
                        "merkle_root": b.get("merkle_root"),
                        "tx_hash": b.get("tx_hash"),
                        "block_number": b.get("block_number"),
                        "chain_name": b.get("chain_name"),
                        "chain_id": b.get("chain_id"),
                        "contract_address": b.get("contract_address"),
                        "anchored_at": b.get("created_at"),
                        "batch_status": b.get("status"),
                    }
                )
        except Exception:
            logger.exception("fetch_merkle_onchain supabase failed hash=%s", h[:16])

    return None
