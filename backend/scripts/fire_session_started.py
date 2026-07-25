#!/usr/bin/env python3
"""
Fire browser-like PostHog `session_started` events for end-to-end Live Events checks.

Mirrors the frontend payload from ChatInterface + posthog-js identify/capture:
  - distinct_id = session_id (anonymous)
  - $set_once via identify-equivalent properties where useful
  - properties: session_id, locale, is_embedded, referrer

Usage (from backend/ with venv):

  python scripts/fire_session_started.py
  python scripts/fire_session_started.py --count 3 --locale ja
  python scripts/fire_session_started.py --key phc_xxx   # override
  python scripts/fire_session_started.py --from-frontend # scrape Vercel build key

Key resolution order:
  1. --key
  2. POSTHOG_KEY / NEXT_PUBLIC_POSTHOG_KEY env
  3. backend/.env (POSTHOG_KEY)
  4. --from-frontend (or auto if still missing): public key from production JS
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_CHUNK_URL = (
    "https://qt-drive-innovations.vercel.app/"
    "_next/static/chunks/app/%5Blocale%5D/page-1b874bbfcf2f91f3.js"
)
# Fallback: discover chunk from /en HTML if hashed filename changes
FRONTEND_PAGE = "https://qt-drive-innovations.vercel.app/en"
POSTHOG_CAPTURE = "https://us.i.posthog.com/capture/"
POSTHOG_BATCH = "https://us.i.posthog.com/batch/"


def load_dotenv_simple(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def discover_key_from_frontend() -> str | None:
    """Pull public project API key from the live Vercel bundle (same as browser)."""
    try:
        html = urllib.request.urlopen(FRONTEND_PAGE, timeout=30).read().decode(
            "utf-8", "ignore"
        )
        chunks = re.findall(
            r"/_next/static/chunks/app/%5Blocale%5D/page-[a-f0-9]+\.js", html
        )
        urls = [FRONTEND_CHUNK_URL]
        for c in chunks:
            urls.insert(0, "https://qt-drive-innovations.vercel.app" + c)
        for url in urls:
            try:
                body = urllib.request.urlopen(url, timeout=30).read().decode(
                    "utf-8", "ignore"
                )
            except urllib.error.HTTPError:
                continue
            m = re.search(r"phc_[A-Za-z0-9]+", body)
            if m:
                return m.group(0)
    except Exception as exc:
        print(f"frontend key discovery failed: {exc}", file=sys.stderr)
    return None


def resolve_key(cli_key: str | None, from_frontend: bool) -> str:
    if cli_key and cli_key.strip():
        return cli_key.strip()
    for name in ("POSTHOG_KEY", "NEXT_PUBLIC_POSTHOG_KEY"):
        v = (os.environ.get(name) or "").strip()
        if v.startswith("phc_"):
            return v
    if from_frontend or True:
        found = discover_key_from_frontend()
        if found:
            return found
    raise SystemExit(
        "No PostHog key. Set POSTHOG_KEY, pass --key, or use --from-frontend."
    )


def post_json(url: str, payload: dict) -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "qt-drive-session-started-script/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status, resp.read().decode("utf-8", "ignore")


def fire_session_started(
    api_key: str,
    session_id: str,
    locale: str,
    *,
    is_embedded: bool,
    referrer: str,
) -> None:
    """
    Browser-like sequence:
      1) $identify with distinct_id = session_id (anonymous)
      2) session_started capture with the same properties as ChatInterface
    """
    # 1) identify (posthog-js identify → $identify)
    identify_payload = {
        "api_key": api_key,
        "event": "$identify",
        "distinct_id": session_id,
        "properties": {
            "$anon_distinct_id": session_id,
            "session_id": session_id,
        },
    }
    status, body = post_json(POSTHOG_CAPTURE, identify_payload)
    if status >= 300:
        raise RuntimeError(f"$identify failed {status}: {body}")

    # 2) session_started — match frontend property names exactly
    capture_payload = {
        "api_key": api_key,
        "event": "session_started",
        "distinct_id": session_id,
        "properties": {
            "session_id": session_id,
            "locale": locale,
            "is_embedded": is_embedded,
            "referrer": referrer,
            # Helps filter test traffic in PostHog
            "$lib": "qt-drive-fire-session-started-script",
            "source": "browser_like_test_script",
            "app": "qt-drive-innovations",
            "environment": "production-verify",
        },
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    }
    status, body = post_json(POSTHOG_CAPTURE, capture_payload)
    if status >= 300:
        raise RuntimeError(f"session_started failed {status}: {body}")
    print(f"  OK session_started distinct_id={session_id} status={status} body={body}")


def main() -> int:
    load_dotenv_simple(ROOT / ".env")

    parser = argparse.ArgumentParser(
        description="Fire browser-like PostHog session_started test events"
    )
    parser.add_argument("--count", type=int, default=2, help="Number of sessions (default 2)")
    parser.add_argument("--locale", default="en", choices=("en", "ja"))
    parser.add_argument(
        "--embedded",
        action="store_true",
        help="Set is_embedded=true (WordPress iframe style)",
    )
    parser.add_argument(
        "--referrer",
        default="https://www.qualitex-trading.com/diagnostic-assistant",
        help="document.referrer-style property",
    )
    parser.add_argument("--key", default="", help="PostHog project API key (phc_…)")
    parser.add_argument(
        "--from-frontend",
        action="store_true",
        help="Force key discovery from live Vercel JS bundle",
    )
    parser.add_argument(
        "--prefix",
        default="browser-like-session",
        help="Prefix for generated session ids",
    )
    args = parser.parse_args()

    if args.count < 1 or args.count > 20:
        print("--count must be 1–20")
        return 1

    key = resolve_key(args.key or None, args.from_frontend)
    print(f"Using PostHog key phc_…{key[-6:]} (len={len(key)})")
    print(f"Firing {args.count} session_started event(s), locale={args.locale}")

    ids: list[str] = []
    for i in range(args.count):
        sid = f"{args.prefix}-{int(time.time())}-{i+1}-{uuid.uuid4().hex[:8]}"
        ids.append(sid)
        fire_session_started(
            key,
            sid,
            args.locale,
            is_embedded=args.embedded,
            referrer=args.referrer if args.embedded else "https://qt-drive-innovations.vercel.app/en",
        )
        time.sleep(0.15)

    print("\n=== Check PostHog → Activity / Live events ===")
    print("Event name: session_started")
    print("Filter properties: source = browser_like_test_script")
    print("distinct_id / session_id values:")
    for sid in ids:
        print(f"  - {sid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
