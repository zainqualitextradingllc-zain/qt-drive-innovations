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
        print("OK: posthog_configured=true")

    sid = f"railway-ph-verify-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    email = (
        f"keep-{sid[:12]}@qualitex-trading.com"
        if args.keep_row
        else f"railway-verify-{uuid.uuid4().hex[:8]}@example.com"
    )
    print("\n=== LEAD CAPTURE (server should emit lead_captured) ===")
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

    print("\n=== PostHog Live Events ===")
    print("Look for event: lead_captured")
    print(f"distinct_id / session_id: {sid}")
    print("properties: contact_method=email, diagnosis_category=brakes, locale=en")
    print("(no contact_value is sent to PostHog — PII stays in diagnostic_leads only)")
    if not args.keep_row:
        print(
            "\nNote: this test used @example.com — run cleanup_test_leads.py afterwards."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
