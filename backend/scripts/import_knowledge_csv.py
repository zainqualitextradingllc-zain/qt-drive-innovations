#!/usr/bin/env python3
"""
Non-technical-friendly knowledge import from CSV → Supabase knowledge_entries
→ OpenAI embeddings.

1. Fill backend/data/knowledge_import_template.csv (or your own copy)
2. From backend/ with venv + .env (DATABASE_URL + OPENAI_API_KEY):

     python scripts/import_knowledge_csv.py data/knowledge_import_template.csv
     python scripts/import_knowledge_csv.py path/to/my_issues.csv --dry-run

CSV columns (header required):
  entry_type (symptom|obd_code|general_repair)
  obd_code (optional, e.g. P0300)
  title_en, description_en, likely_causes_en (semicolon-separated)
  severity_en, recommended_action_en
  estimated_cost_usd_min, estimated_cost_usd_max
  title_ja, description_ja, likely_causes_ja (semicolon-separated)
  severity_ja, recommended_action_ja
  estimated_cost_jpy_min, estimated_cost_jpy_max
  embed_text (optional; auto-built if blank)

Rows are upserted by title_en (skip if title already exists unless --force).
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
sys.path.insert(0, str(ROOT))

import psycopg  # noqa: E402
from app.services.embeddings import build_embed_text, embed_texts_sync  # noqa: E402

REQUIRED = [
    "entry_type",
    "title_en",
    "description_en",
    "likely_causes_en",
    "severity_en",
    "recommended_action_en",
    "estimated_cost_usd_min",
    "estimated_cost_usd_max",
    "title_ja",
    "description_ja",
    "likely_causes_ja",
    "severity_ja",
    "recommended_action_ja",
    "estimated_cost_jpy_min",
    "estimated_cost_jpy_max",
]


def split_causes(val: str) -> list[str]:
    if not val or not str(val).strip():
        return []
    return [p.strip() for p in str(val).replace("|", ";").split(";") if p.strip()]


def as_int(val) -> int | None:
    if val is None or str(val).strip() == "":
        return None
    return int(float(str(val).replace(",", "").strip()))


def main() -> int:
    parser = argparse.ArgumentParser(description="Import knowledge CSV + embed")
    parser.add_argument("csv_path", type=str)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-embed existing titles (does not rewrite text fields)",
    )
    args = parser.parse_args()

    path = Path(args.csv_path)
    if not path.is_file():
        # allow relative to backend/
        alt = ROOT / args.csv_path
        if alt.is_file():
            path = alt
        else:
            print(f"File not found: {args.csv_path}")
            return 1

    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url.startswith("postgres"):
        print("DATABASE_URL required")
        return 1

    from app.config import get_settings

    if not get_settings().openai_configured and not args.dry_run:
        print("OPENAI_API_KEY required to embed (or use --dry-run)")
        return 1

    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            print("Empty CSV")
            return 1
        missing = [c for c in REQUIRED if c not in reader.fieldnames]
        if missing:
            print(f"Missing columns: {missing}")
            print(f"Found: {reader.fieldnames}")
            return 1
        rows = list(reader)

    print(f"Loaded {len(rows)} row(s) from {path}")
    if args.dry_run:
        for r in rows:
            print(f"  would import: {r.get('title_en')!r} / {r.get('title_ja')!r}")
        return 0

    inserted = skipped = embedded = 0
    with psycopg.connect(url, connect_timeout=30) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            for r in rows:
                title = (r.get("title_en") or "").strip()
                if not title:
                    print("  skip blank title_en")
                    continue
                cur.execute(
                    "select id, embedding is not null from knowledge_entries where title_en = %s",
                    (title,),
                )
                existing = cur.fetchone()
                if existing and not args.force:
                    print(f"  skip existing: {title}")
                    skipped += 1
                    row_id = existing[0]
                    has_emb = existing[1]
                    if has_emb:
                        continue
                elif existing:
                    row_id = existing[0]
                else:
                    causes_en = split_causes(r.get("likely_causes_en") or "")
                    causes_ja = split_causes(r.get("likely_causes_ja") or "")
                    obd = (r.get("obd_code") or "").strip() or None
                    embed_text = (r.get("embed_text") or "").strip() or None
                    cur.execute(
                        """
                        insert into knowledge_entries (
                          entry_type, obd_code,
                          title_en, description_en, likely_causes_en,
                          severity_en, recommended_action_en,
                          estimated_cost_usd_min, estimated_cost_usd_max,
                          title_ja, description_ja, likely_causes_ja,
                          severity_ja, recommended_action_ja,
                          estimated_cost_jpy_min, estimated_cost_jpy_max,
                          embed_text, source
                        ) values (
                          %s, %s, %s, %s, %s, %s, %s, %s, %s,
                          %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        returning id
                        """,
                        (
                            (r.get("entry_type") or "symptom").strip(),
                            obd,
                            title,
                            r.get("description_en") or title,
                            causes_en,
                            r.get("severity_en") or "Caution",
                            r.get("recommended_action_en") or "Inspect at a workshop",
                            as_int(r.get("estimated_cost_usd_min")),
                            as_int(r.get("estimated_cost_usd_max")),
                            r.get("title_ja") or title,
                            r.get("description_ja") or r.get("description_en") or title,
                            causes_ja or causes_en,
                            r.get("severity_ja") or "注意",
                            r.get("recommended_action_ja")
                            or "整備工場で点検してください",
                            as_int(r.get("estimated_cost_jpy_min")),
                            as_int(r.get("estimated_cost_jpy_max")),
                            embed_text,
                            "csv_import",
                        ),
                    )
                    row_id = cur.fetchone()[0]
                    inserted += 1
                    print(f"  + inserted: {title}")

                # Embed
                cur.execute(
                    """
                    select id, entry_type, obd_code, title_en, description_en,
                           likely_causes_en, severity_en, recommended_action_en,
                           title_ja, description_ja, likely_causes_ja,
                           severity_ja, recommended_action_ja, embed_text
                    from knowledge_entries where id = %s
                    """,
                    (row_id,),
                )
                cols = [d.name for d in cur.description]
                doc = dict(zip(cols, cur.fetchone()))
                text = build_embed_text(doc)
                try:
                    vec = embed_texts_sync([text])[0]
                    cur.execute(
                        """
                        update knowledge_entries
                        set embedding = %s::vector, embed_text = %s, updated_at = now()
                        where id = %s
                        """,
                        (vec, text, row_id),
                    )
                    embedded += 1
                    print(f"  OK embed: {title}")
                except Exception as exc:
                    print(f"  FAIL embed {title}: {exc}")
                time.sleep(0.1)

    print(f"Done. inserted={inserted} skipped={skipped} embedded={embedded}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
