"""Phase 4a.0 — public verification of diagnosis content hashes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services.attestation import (
    fetch_attestation_by_hash,
    fetch_merkle_onchain,
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

    # Phase 4a.1 QT ProofChain™ — additive only; does not affect hash validity
    merkle = fetch_merkle_onchain(stored_hash)
    legacy_tx = row.get("tx_hash")
    anchored = bool(merkle and merkle.get("tx_hash")) or bool(legacy_tx)
    if merkle and merkle.get("tx_hash"):
        on_chain = {
            "anchored": True,
            "status": "confirmed",
            "message_en": "On-Chain Confirmed (Merkle batch anchored)",
            "message_ja": "オンチェーン確認済み（Merkle バッチでアンカー済み）",
            "tx_hash": merkle.get("tx_hash"),
            "explorer_url": merkle.get("explorer_url"),
            "merkle_root": merkle.get("merkle_root"),
            "proof": merkle.get("proof"),
            "leaf_hash": merkle.get("leaf_hash"),
            "leaf_index": merkle.get("leaf_index"),
            "batch_id": merkle.get("batch_id"),
            "chain_name": merkle.get("chain_name"),
            "chain_id": merkle.get("chain_id"),
            "block_number": merkle.get("block_number"),
            "contract_address": merkle.get("contract_address"),
            "anchored_at": merkle.get("anchored_at"),
        }
    elif legacy_tx:
        on_chain = {
            "anchored": True,
            "status": "confirmed",
            "message_en": "On-Chain Confirmed",
            "message_ja": "オンチェーン確認済み",
            "tx_hash": legacy_tx,
            "explorer_url": None,
            "chain_id": row.get("chain_id"),
        }
    else:
        on_chain = {
            "anchored": False,
            "status": "pending",
            "message_en": "Pending on-chain anchoring",
            "message_ja": "オンチェーン・アンカー待ち",
            "tx_hash": None,
            "explorer_url": None,
        }

    return {
        "found": True,
        "valid": valid,
        "content_hash": stored_hash,
        "recomputed_hash": recomputed,
        "diagnosis_id": row.get("diagnosis_id"),
        "session_id": row.get("session_id"),
        "created_at": row.get("created_at"),
        "anchor_status": (
            "anchored"
            if anchored
            else (row.get("anchor_status") or "hashed")
        ),
        "chain_id": (merkle or {}).get("chain_id") or row.get("chain_id"),
        "tx_hash": (merkle or {}).get("tx_hash") or legacy_tx,
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
        "on_chain": on_chain,
    }
