#!/usr/bin/env python3
"""
Quality checks for RAG follow-ups:
  1) Strong match → hard-quoted cost from knowledge (150-400 USD for grinding)
  2) Similarity threshold filtering (weak hits dropped)
  3) Multilingual JP query still retrieves battery entry as strong
  4) Unknown symptom → no strong hits (general GPT fallback path)

Usage (backend/ venv + .env):
  python scripts/test_rag_quality.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402
from app.tools.rag import (  # noqa: E402
    apply_grounded_cost,
    filter_strong_hits,
    format_grounded_cost,
    search_repair_knowledge,
)
from app.services.embeddings import embed_query  # noqa: E402


async def retrieve(q: str, lang: str = "en"):
    emb = await embed_query(q)
    raw = await search_repair_knowledge(
        query=q, language=lang, top_k=5, query_embedding=emb
    )
    min_sim = float(get_settings().rag_min_similarity)
    strong = filter_strong_hits(raw, min_similarity=min_sim)
    return raw, strong, min_sim


async def main() -> int:
    settings = get_settings()
    if not settings.openai_configured:
        print("OPENAI_API_KEY required")
        return 1

    fails = 0
    print(f"rag_min_similarity={settings.rag_min_similarity}\n")

    # --- 1) Cost hard-quote ---
    print("=== 1) Hard-quoted cost (brakes grinding) ===")
    raw, strong, thr = await retrieve("brakes grinding squeaking when I stop")
    print(f"  raw={len(raw)} strong={len(strong)} thr={thr}")
    if not strong:
        print("  FAIL: expected strong hit for grinding brakes")
        fails += 1
    else:
        top = strong[0]
        print(f"  top={top.get('title_en') or top.get('title')} sim={top.get('similarity')}")
        cost = format_grounded_cost(top, "en")
        print(f"  grounded_cost={cost}")
        fake_llm = {
            "estimated_cost": "200-600 USD",
            "currency": "USD",
            "cost_min": 200,
            "cost_max": 600,
            "language": "en",
            "diagnosis": [{"cause": "x", "confidence": 70}],
            "severity": "Caution",
            "severity_code": "caution",
            "next_action": "Inspect",
            "disclaimer": "test",
        }
        fixed = apply_grounded_cost(fake_llm, strong, "en")
        print(f"  after_apply estimated_cost={fixed.get('estimated_cost')!r}")
        if fixed.get("estimated_cost") != "150-400 USD":
            print("  FAIL: expected estimated_cost exactly '150-400 USD'")
            fails += 1
        else:
            print("  OK hard quote overwrote LLM 200-600 → 150-400 USD")

    # --- 2) Threshold vs JP battery (~0.56) ---
    print("\n=== 2) JP battery vs threshold ===")
    raw, strong, thr = await retrieve("バッテリーが上がってセルが回らない", "ja")
    if raw:
        print(f"  top_raw sim={raw[0].get('similarity')} title={raw[0].get('title_en')}")
    print(f"  strong={len(strong)} (need >=1 if sim>={thr})")
    if not strong:
        print("  FAIL: JP battery should be strong at default 0.55")
        fails += 1
    else:
        sim = float(raw[0].get("similarity") or 0)
        print(f"  OK sim={sim:.3f} >= {thr} → strong match")

    # --- 3) Unknown symptom: steering vibration (not in original 10) ---
    print("\n=== 3) Fallback — unknown / weak symptom ===")
    # Prefer a phrase unlikely to match unless user imported the template row
    q = "my glove box light is flickering only when raining"
    raw, strong, thr = await retrieve(q)
    print(f"  query={q!r}")
    for h in raw[:3]:
        print(
            f"    raw sim={h.get('similarity')} strong={h in strong} "
            f"| {h.get('title_en') or h.get('title')}"
        )
    if strong:
        # Accept only if similarity is clearly high (accidental real match)
        top_sim = float(strong[0].get("similarity") or 0)
        if top_sim >= 0.70:
            print(f"  NOTE: unexpected strong match sim={top_sim:.3f} — check KB growth")
        else:
            print(
                f"  FAIL: weak hit sim={top_sim:.3f} passed as strong "
                f"(threshold may be too low)"
            )
            fails += 1
    else:
        print("  OK no strong match → general GPT path (no forced grounding)")

    # Also report highway vibration retrieval (may match suspension-ish weakly)
    print("\n=== 3b) steering wheel vibrates at highway speed ===")
    raw, strong, thr = await retrieve("steering wheel vibrates at highway speed")
    for h in raw[:3]:
        sim = h.get("similarity")
        is_s = h in strong
        print(f"    sim={sim} strong={is_s} | {h.get('title_en') or h.get('title')}")
    if not strong:
        print("  OK no strong KB match for highway vibration → general knowledge")
    else:
        print(
            f"  strong top={strong[0].get('title_en')} "
            f"sim={strong[0].get('similarity')} (OK if user imported template)"
        )

    print(f"\n=== RESULT fails={fails} ===")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
