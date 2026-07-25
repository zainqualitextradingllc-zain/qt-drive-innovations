#!/usr/bin/env python3
"""
Delete diagnostic_leads rows used for automated tests
(contact_value ILIKE '%example.com%').

Usage (from backend/ with venv + DATABASE_URL):

  python scripts/cleanup_test_leads.py --dry-run
  python scripts/cleanup_test_leads.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
sys.path.insert(0, str(ROOT))

import psycopg  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean test diagnostic_leads rows")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url.startswith("postgres"):
        print("DATABASE_URL required")
        return 1

    pattern = "%example.com%"
    with psycopg.connect(url, connect_timeout=20) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, session_id, contact_value, created_at
                from public.diagnostic_leads
                where contact_value ilike %s
                order by created_at
                """,
                (pattern,),
            )
            rows = cur.fetchall()
            print(f"Matched {len(rows)} row(s) with contact_value ILIKE '{pattern}'")
            for r in rows:
                print(f"  {r[0]}  {r[1]}  {r[2]}  {r[3]}")

            if args.dry_run:
                print("Dry-run: no deletes")
                return 0

            if not rows:
                print("Nothing to delete")
                return 0

            cur.execute(
                """
                delete from public.diagnostic_leads
                where contact_value ilike %s
                """,
                (pattern,),
            )
            print(f"Deleted {cur.rowcount} row(s)")

            cur.execute("select count(*) from public.diagnostic_leads")
            print("Remaining leads:", cur.fetchone()[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
