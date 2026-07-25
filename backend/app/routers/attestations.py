"""Phase 4a.0 — public verification of diagnosis content hashes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services.attestation import (
    fetch_attestation_by_hash,
    serialize_canonical,
    sha256_hex,
    verify_content_hash,
)

router = APIRouter(prefix="/api/attestations", tags=["attestations"])


@router.get("/verify")
async def verify_attestation(
    h: str = Query(..., min_length=32, max_length=128, description="SHA-256 content_hash"),
):
    """
    Public lookup: re-serialize canonical_json, re-hash SHA-256, compare to stored hash.
    No auth. No PII in stored payload.
    """
    row = fetch_attestation_by_hash(h)
    if not row:
        raise HTTPException(status_code=404, detail="attestation_not_found")

    canonical = row.get("canonical_json") or {}
    if isinstance(canonical, str):
        import json

        canonical = json.loads(canonical)

    stored_hash = (row.get("content_hash") or "").lower()
    recomputed = sha256_hex(serialize_canonical(canonical))
    valid = verify_content_hash(canonical, stored_hash)

    causes = canonical.get("causes") or []
    top = causes[0] if causes else None
    vehicle = canonical.get("vehicle") or {}

    return {
        "found": True,
        "valid": valid,
        "content_hash": stored_hash,
        "recomputed_hash": recomputed,
        "diagnosis_id": row.get("diagnosis_id"),
        "session_id": row.get("session_id"),
        "created_at": row.get("created_at"),
        "anchor_status": row.get("anchor_status") or "hashed",
        "chain_id": row.get("chain_id"),
        "tx_hash": row.get("tx_hash"),
        "summary": {
            "locale": canonical.get("locale"),
            "timestamp": canonical.get("timestamp"),
            "model_version": canonical.get("model_version"),
            "vehicle": vehicle,
            "top_cause": (top or {}).get("cause"),
            "top_confidence": (top or {}).get("confidence"),
            "cost_min": canonical.get("cost_min"),
            "cost_max": canonical.get("cost_max"),
            "causes": causes,
        },
        "on_chain": {
            "anchored": bool(row.get("tx_hash")),
            "message_en": "On-chain proof: Not yet anchored (coming in a future update)",
            "message_ja": "オンチェーン証明: まだアンカーされていません（今後のアップデートで対応予定）",
        },
    }
