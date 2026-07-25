#!/usr/bin/env python3
"""Compare Vercel / local / Railway PostHog keys and probe capture hosts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

RAILWAY = "https://qt-drive-innovations-production.up.railway.app"
FRONTEND = "https://qt-drive-innovations.vercel.app/en"


def scrape_vercel_key() -> str:
    html = urllib.request.urlopen(FRONTEND, timeout=30).read().decode("utf-8", "ignore")
    chunks = re.findall(
        r"/_next/static/chunks/app/%5Blocale%5D/page-[a-f0-9]+\.js", html
    )
    if not chunks:
        raise RuntimeError("no page chunk in frontend HTML")
    body = urllib.request.urlopen(
        "https://qt-drive-innovations.vercel.app" + chunks[0], timeout=30
    ).read().decode("utf-8", "ignore")
    m = re.search(r"phc_[A-Za-z0-9]+", body)
    if not m:
        raise RuntimeError("no phc_ key in frontend bundle")
    return m.group(0)


def key_meta(k: str | None) -> dict:
    if not k:
        return {"present": False}
    k = k.strip().strip('"').strip("'")
    return {
        "present": True,
        "length": len(k),
        "prefix12": k[:12],
        "mid8": k[20:28] if len(k) >= 28 else None,
        "suffix8": k[-8:] if len(k) >= 8 else None,
        "sha256_12": hashlib.sha256(k.encode("utf-8")).hexdigest()[:12],
        "has_whitespace": k != k.strip() or any(c.isspace() for c in k),
        "starts_phc": k.startswith("phc_"),
    }


def capture(host: str, key: str, distinct_id: str, source: str) -> dict:
    payload = {
        "api_key": key,
        "event": "lead_captured",
        "distinct_id": distinct_id,
        "properties": {
            "session_id": distinct_id,
            "contact_method": "email",
            "diagnosis_category": "diagnose",
            "locale": "en",
            "source": source,
            "$lib": "qt-drive-diagnose-script",
            "$lib_version": "1.0.0",
        },
    }
    with httpx.Client(timeout=15.0) as client:
        r = client.post(f"{host.rstrip('/')}/capture/", json=payload)
    return {
        "host": host,
        "http_status": r.status_code,
        "body": (r.text or "")[:120],
        "distinct_id": distinct_id,
        "source": source,
    }


def main() -> int:
    vercel = scrape_vercel_key()
    local = (os.getenv("POSTHOG_KEY") or "").strip().strip('"').strip("'")

    railway_health = json.loads(
        urllib.request.urlopen(f"{RAILWAY}/health", timeout=30).read().decode()
    )
    railway_probe = json.loads(
        urllib.request.urlopen(f"{RAILWAY}/health/posthog", timeout=30).read().decode()
    )

    print("=== KEY META ===")
    print("VERCEL", json.dumps(key_meta(vercel), indent=2))
    print("LOCAL ", json.dumps(key_meta(local), indent=2))
    print("LOCAL_EQUALS_VERCEL", local == vercel)
    print(
        "RAILWAY_HEALTH",
        {
            "fingerprint": railway_health.get("posthog_key_fingerprint"),
            "length": railway_health.get("posthog_key_length"),
            "sha_field": railway_health.get("posthog_key_sha12"),
            "mid8": railway_health.get("posthog_key_mid8"),
        },
    )
    print("RAILWAY_PROBE", json.dumps(railway_probe, indent=2)[:800])

    ts = int(time.time())
    print("\n=== LOCAL CAPTURE PROBES (should appear if key+region OK) ===")
    for host, tag in (
        ("https://us.i.posthog.com", "us"),
        ("https://eu.i.posthog.com", "eu"),
    ):
        sid = f"diag-local-{tag}-{ts}"
        res = capture(host, vercel, sid, f"diag_local_{tag}")
        print(json.dumps(res))

    print("\n=== SEARCH IN POSTHOG ===")
    print(f"  diag-local-us-{ts}")
    print(f"  diag-local-eu-{ts}")
    print(f"  {railway_probe.get('probe_session_id')}")
    print("  HogQL: event = 'lead_captured' AND properties.source LIKE 'diag_local%'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
