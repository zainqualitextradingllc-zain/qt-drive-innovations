#!/usr/bin/env python3
"""
Backfill knowledge_entries.embedding for QT Drive Innovations RAG.

Prerequisites:
  1. Run supabase/migrations/001_knowledge_base.sql
  2. Run supabase/seed/seed_knowledge.sql
  3. Set in backend/.env:
       OPENAI_API_KEY=sk-...
       SUPABASE_URL=https://xxxx.supabase.co
       SUPABASE_SERVICE_ROLE_KEY=...

Usage (from backend/ with venv active):

  python scripts/backfill_embeddings.py --dry-run
  python scripts/backfill_embeddings.py
  python scripts/backfill_embeddings.py --force --limit 50
  python scripts/backfill_embeddings.py --verify "brakes grinding"
  python scripts/backfill_embeddings.py --verify "ブレーキ きしむ"

After all rows have embeddings, run:
  supabase/migrations/002_vector_index.sql
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Allow `python scripts/backfill_embeddings.py` from backend/
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from app.config import get_settings  # noqa: E402
from app.services.embeddings import (  # noqa: E402
    EXPECTED_DIMS,
    build_embed_text,
    embed_texts_sync,
)


def get_supabase():
    settings = get_settings()
    if not settings.supabase_configured:
        raise SystemExit(
            "Supabase is not configured.\n"
            "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in backend/.env "
            "(not the placeholder values)."
        )
    if not settings.openai_configured:
        raise SystemExit(
            "OpenAI is not configured.\n"
            "Set OPENAI_API_KEY in backend/.env (required for text-embedding-3-small)."
        )

    from supabase import create_client

    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def fetch_rows(client, *, force: bool, limit: int | None) -> list[dict]:
    """
    Fetch knowledge rows needing embeddings.
    Note: filtering null embeddings via PostgREST can be awkward; we filter client-side.
    """
    q = client.table("knowledge_entries").select(
        "id, entry_type, obd_code, title_en, description_en, likely_causes_en, "
        "severity_en, recommended_action_en, title_ja, description_ja, likely_causes_ja, "
        "severity_ja, recommended_action_ja, embed_text, embedding"
    )
    # Prefer oldest first so partial runs are stable
    q = q.order("created_at", desc=False)
    # Pull a generous page; re-run script to continue
    fetch_limit = limit if limit and force else max(limit or 500, 500)
    resp = q.limit(fetch_limit).execute()
    rows = list(resp.data or [])

    if force:
        selected = rows
    else:
        selected = [r for r in rows if r.get("embedding") is None]

    if limit is not None:
        selected = selected[:limit]
    return selected


def update_embedding(client, row_id: str, embedding: list[float], embed_text: str) -> None:
    client.table("knowledge_entries").update(
        {
            "embedding": embedding,
            "embed_text": embed_text,
        }
    ).eq("id", row_id).execute()


def verify_search(client, query: str, top_k: int = 5) -> None:
    print(f"\n=== VERIFY: match_knowledge_entries for {query!r} ===")
    vectors = embed_texts_sync([query])
    query_embedding = vectors[0]
    try:
        rpc = client.rpc(
            "match_knowledge_entries",
            {
                "query_embedding": query_embedding,
                "match_threshold": 0.3,
                "match_count": top_k,
            },
        ).execute()
    except Exception as exc:
        print(f"RPC failed: {exc}")
        print("Ensure 001_knowledge_base.sql was applied (match_knowledge_entries function).")
        return

    data = rpc.data or []
    if not data:
        print("No matches (threshold too high, or embeddings missing).")
        return

    for i, row in enumerate(data, 1):
        sim = row.get("similarity")
        sim_s = f"{sim:.3f}" if isinstance(sim, (int, float)) else "?"
        print(
            f"{i}. sim={sim_s} | {row.get('obd_code') or row.get('entry_type')} | "
            f"{row.get('title_en')} / {row.get('title_ja')}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill OpenAI embeddings into knowledge_entries for pgvector RAG."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List rows that would be embedded; do not call OpenAI or write DB.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-embed all rows (even if embedding already set).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of rows to process this run.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="OpenAI embedding batch size (default 32).",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.2,
        help="Seconds to sleep between batches (rate-limit friendly).",
    )
    parser.add_argument(
        "--verify",
        type=str,
        default=None,
        metavar="QUERY",
        help="After backfill (or alone with --verify-only), run a similarity search smoke test.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Skip backfill; only run --verify search.",
    )
    args = parser.parse_args()

    settings = get_settings()
    print("QT Drive Innovations — embedding backfill")
    print(f"  model:     {settings.openai_embedding_model}")
    print(f"  dims:      {EXPECTED_DIMS}")
    print(f"  supabase:  {settings.supabase_url}")
    print(f"  dry_run:   {args.dry_run}")
    print(f"  force:     {args.force}")

    client = get_supabase()

    if args.verify_only:
        if not args.verify:
            print("--verify-only requires --verify QUERY")
            return 2
        verify_search(client, args.verify)
        return 0

    rows = fetch_rows(client, force=args.force, limit=args.limit)
    print(f"\nRows to process: {len(rows)}")

    if not rows:
        print("Nothing to do (all embeddings present). Use --force to re-embed.")
        if args.verify:
            verify_search(client, args.verify)
        return 0

    for r in rows[:10]:
        preview = build_embed_text(r)[:80].replace("\n", " ")
        print(f"  - {r['id'][:8]}… | {r.get('title_en') or r.get('obd_code')} | {preview}…")
    if len(rows) > 10:
        print(f"  … and {len(rows) - 10} more")

    if args.dry_run:
        print("\nDry run complete — no API calls or DB writes.")
        return 0

    batch_size = max(1, args.batch_size)
    updated = 0
    errors = 0

    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        texts = [build_embed_text(r) for r in batch]
        try:
            vectors = embed_texts_sync(texts)
        except Exception as exc:
            print(f"\nBatch embed failed at offset {start}: {exc}")
            errors += len(batch)
            continue

        for row, text, vec in zip(batch, texts, vectors):
            try:
                update_embedding(client, row["id"], vec, text)
                updated += 1
                print(f"  OK {row['id'][:8]}… ({len(vec)} dims)")
            except Exception as exc:
                errors += 1
                print(f"  FAIL {row['id']}: {exc}")

        if args.sleep > 0 and start + batch_size < len(rows):
            time.sleep(args.sleep)

    print(f"\nDone. updated={updated} errors={errors}")

    if args.verify:
        verify_search(client, args.verify)

    if updated > 0 and not args.force:
        print(
            "\nNext: when most rows have embeddings, run in Supabase SQL Editor:\n"
            "  supabase/migrations/002_vector_index.sql"
        )

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
