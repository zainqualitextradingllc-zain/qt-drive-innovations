#!/usr/bin/env python3
"""
Verify Railway production has PostHog wired for lead_captured.

1. GET /health → posthog_configured must be true
2. POST /leads/capture with a unique session_id (PII uses @example.com only if --keep-row)
3. Prints the session_id to find as lead_captured in PostHog Live Events

Usage:
  python scripts/verify_posthog_railway.py
  python scripts/verify_posthog_railway.py --api https://qt-drive-innovations-production.up.railway.app
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid


DEFAULT_API = "https://qt-drive-innovations-production.up.railway.app"


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())


def post_json(url: str, payload: dict) -> tuple[int, dict | str]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode()
            try:
                return r.status, json.loads(body)
            except json.JSONDecodeError:
                return r.status, body
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--api", default=DEFAULT_API)
    p.add_argument(
        "--keep-row",
        action="store_true",
        help="Do not use @example.com (keeps row out of cleanup_test_leads pattern)",
    )
    args = p.parse_args()
    api = args.api.rstrip("/")

    print("=== HEALTH ===")
    health = get_json(f"{api}/health")
    print(json.dumps(health, indent=2))
    ph = health.get("posthog_configured")
    suffix = health.get("posthog_key_suffix")
    if ph is None:
        print(
            "WARN: posthog_configured missing — deploy latest health.py first",
            file=sys.stderr,
        )
    elif not ph:
        print(
            "FAIL: posthog_configured=false. Set Railway env POSTHOG_KEY "
            "to the same phc_… token as Vercel NEXT_PUBLIC_POSTHOG_KEY, then redeploy.",
            file=sys.stderr,
        )
        return 2
    else:
        print(f"OK: posthog_configured=true key_suffix=…{suffix}")

    # IMPORTANT: this call is SERVER-ONLY. We intentionally do NOT also POST
    # to PostHog from this script. If lead_captured never appears for `sid`,
    # Railway POSTHOG_KEY is wrong, missing, or capture is failing.
    # (Do not confuse with older live-verify-lead-* IDs that were dual-fired
    # from the client-side capture script.)
    sid = f"server-only-lead-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    email = (
        f"keep-{sid[:12]}@qualitex-trading.com"
        if args.keep_row
        else f"railway-verify-{uuid.uuid4().hex[:8]}@example.com"
    )
    print("\n=== LEAD CAPTURE (Railway background task → PostHog only) ===")
    status, body = post_json(
        f"{api}/leads/capture",
        {
            "session_id": sid,
            "contact_method": "email",
            "diagnosis_category": "brakes",
            "locale": "en",
            "contact_value": email,
        },
    )
    print("status", status, body)
    if status != 200:
        print("FAIL: leads capture", file=sys.stderr)
        return 1

    print("\n=== PostHog Live Events (server-only proof) ===")
    print("Event name:  lead_captured")
    print(f"distinct_id: {sid}")
    print("properties:  source=railway_leads_router (after latest deploy)")
    print("             contact_method=email, diagnosis_category=brakes, locale=en")
    print("PII is NOT sent to PostHog (only stored in diagnostic_leads).")
    print()
    print("If this exact distinct_id never appears within ~1–2 minutes:")
    print("  → Railway POSTHOG_KEY does not match Vercel NEXT_PUBLIC_POSTHOG_KEY")
    print("    (or PostHog is rejecting the key). Fix in Railway → Variables.")
    if not args.keep_row:
        print(
            "\nNote: this test used @example.com — run cleanup_test_leads.py afterwards."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
