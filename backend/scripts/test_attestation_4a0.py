#!/usr/bin/env python3
"""Phase 4a.0 checklist tests — hash, PII, verify API, lead capture regression."""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.models.diagnosis import (  # noqa: E402
    DiagnosisCause,
    DiagnosisPayload,
    VehicleContextModel,
)
from app.services.attestation import (  # noqa: E402
    build_canonical_payload,
    compute_content_hash,
    create_diagnosis_attestation,
)


PII_KEYS = {
    "email",
    "phone",
    "line",
    "line_id",
    "name",
    "contact",
    "contact_method",
    "contact_value",
    "vin",  # we intentionally omit VIN from canonical vehicle
}


def _walk_keys(obj, found: set[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            found.add(str(k).lower())
            _walk_keys(v, found)
    elif isinstance(obj, list):
        for i in obj:
            _walk_keys(i, found)


def main() -> int:
    client = TestClient(app)
    failed = 0

    print("=== 1) lead_captured path still registered (regression) ===")
    paths = sorted(client.app.openapi()["paths"].keys())
    assert "/leads/capture" in paths, paths
    assert "/api/attestations/verify" in paths, paths
    # Empty body should 422, not 500 / missing route
    r = client.post("/leads/capture", json={})
    print("  POST /leads/capture empty →", r.status_code, "(expect 422)")
    if r.status_code not in (422, 400):
        print("  FAIL unexpected status")
        failed += 1
    else:
        print("  OK lead endpoint alive")

    print("\n=== 2) Hash deterministic (same inputs twice) ===")
    d = DiagnosisPayload(
        language="en",
        vehicle_context=VehicleContextModel(
            year=2019, make="Toyota", model="Corolla", engine="1.8L"
        ),
        diagnosis=[
            DiagnosisCause(cause="Worn brake pads", confidence=88),
            DiagnosisCause(cause="Warped rotor", confidence=62),
        ],
        severity="Caution",
        severity_code="caution",
        estimated_cost="150-400 USD",
        currency="USD",
        cost_min=150,
        cost_max=400,
        next_action="Inspect",
        disclaimer="AI only",
    )
    fixed = dict(
        diagnosis_id="fixed-diag-id-0001",
        session_id="fixed-session-0001",
        diagnosis=d,
        locale="en",
        timestamp="2026-07-25T12:00:00Z",
    )
    c1 = build_canonical_payload(**fixed)
    c2 = build_canonical_payload(**fixed)
    s1, h1 = compute_content_hash(c1)
    s2, h2 = compute_content_hash(c2)
    print("  run1", h1)
    print("  run2", h2)
    if h1 != h2 or s1 != s2 or len(h1) != 64:
        print("  FAIL not deterministic")
        failed += 1
    else:
        print("  OK same diagnosis → same hash")

    print("\n=== 3) PII absent from canonical_json ===")
    keys: set[str] = set()
    _walk_keys(c1, keys)
    # also scan JSON string for common PII patterns
    blob = json.dumps(c1).lower()
    pii_hits = [k for k in PII_KEYS if k in keys]
    str_hits = []
    for needle in (
        "email",
        "contact_method",
        "contact_value",
        "@example.com",
        "line_id",
    ):
        if needle in blob:
            str_hits.append(needle)
    # VIN must not appear as a field
    if "vin" in keys:
        pii_hits.append("vin")
    print("  keys", sorted(keys))
    if pii_hits or str_hits:
        print("  FAIL PII", pii_hits, str_hits)
        failed += 1
    else:
        print("  OK no PII keys/strings in canonical_json")

    print("\n=== 4) verify page API — fake hash → not found ===")
    fake = "a" * 64
    r = client.get("/api/attestations/verify", params={"h": fake})
    print("  status", r.status_code, r.text[:120])
    if r.status_code != 404:
        print("  FAIL expected 404")
        failed += 1
    else:
        print("  OK not found for fake hash")

    print("\n=== 5) verify page API — real hash → match ===")
    att = create_diagnosis_attestation(
        session_id=f"checklist-{uuid.uuid4().hex[:8]}",
        diagnosis=d,
        locale="en",
    )
    assert att and att.get("content_hash")
    h = att["content_hash"]
    # PII check on saved payload
    saved_keys: set[str] = set()
    _walk_keys(att["canonical_json"], saved_keys)
    if any(k in saved_keys for k in PII_KEYS):
        print("  FAIL PII in saved canonical", saved_keys & PII_KEYS)
        failed += 1
    r = client.get("/api/attestations/verify", params={"h": h})
    body = r.json()
    print("  status", r.status_code, "valid", body.get("valid"))
    if r.status_code != 200 or not body.get("valid"):
        print("  FAIL", body)
        failed += 1
    else:
        # ensure verify response summary has no contact fields
        summary_blob = json.dumps(body.get("summary") or {}).lower()
        if "email" in summary_blob or "contact_method" in summary_blob:
            print("  FAIL PII leaked on verify response")
            failed += 1
        else:
            print("  OK match for real hash; summary clean")

    print("\n=== RESULT ===")
    if failed:
        print(f"FAILED checks: {failed}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
