#!/usr/bin/env python3
"""
RAG proof-of-concept: upsert sample car-issue docs → OpenAI embeddings →
verify vector similarity retrieval.

Uses existing Supabase table `knowledge_entries` (pgvector 1536) and
`match_knowledge_entries` RPC from supabase/migrations/001_knowledge_base.sql.

Prerequisites (backend/.env):
  DATABASE_URL=postgresql://...
  OPENAI_API_KEY=sk-...

Usage (from backend/ with venv):

  python scripts/ingest_knowledge_poc.py              # upsert + embed missing + test
  python scripts/ingest_knowledge_poc.py --status     # counts only
  python scripts/ingest_knowledge_poc.py --test-only  # retrieval smoke only
  python scripts/ingest_knowledge_poc.py --force-embed
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
sys.path.insert(0, str(ROOT))

import psycopg  # noqa: E402
from app.services.embeddings import (  # noqa: E402
    EXPECTED_DIMS,
    build_embed_text,
    embed_texts_sync,
)

# 10 bilingual PoC documents (symptom → causes → cost → severity)
POC_DOCUMENTS: list[dict[str, Any]] = [
    {
        "entry_type": "symptom",
        "obd_code": None,
        "title_en": "Grinding noise when braking",
        "description_en": (
            "A high-pitched or grinding sound occurs when the brake pedal is pressed."
        ),
        "likely_causes_en": [
            "Worn brake pads",
            "Warped rotor",
            "Debris stuck in caliper",
        ],
        "severity_en": "Caution - inspect within 1-2 weeks",
        "recommended_action_en": "Visit mechanic for brake inspection",
        "estimated_cost_usd_min": 150,
        "estimated_cost_usd_max": 400,
        "title_ja": "ブレーキ時にきしむ音がする",
        "description_ja": "ブレーキペダルを踏むと高音またはこすれる音が発生する。",
        "likely_causes_ja": [
            "ブレーキパッドの摩耗",
            "ローターの歪み",
            "キャリパー内の異物",
        ],
        "severity_ja": "注意 - 1〜2週間以内に点検してください",
        "recommended_action_ja": "ブレーキ点検のため整備士に相談してください",
        "estimated_cost_jpy_min": 20000,
        "estimated_cost_jpy_max": 60000,
        "embed_text": (
            "Grinding noise when braking worn pads warped rotor caliper debris "
            "ブレーキ きしむ ゴリゴリ キーキー パッド ローター"
        ),
    },
    {
        "entry_type": "obd_code",
        "obd_code": "P0300",
        "title_en": "Random/Multiple Cylinder Misfire Detected",
        "description_en": (
            "Engine control module has detected misfires across multiple cylinders."
        ),
        "likely_causes_en": [
            "Faulty spark plugs",
            "Bad ignition coils",
            "Fuel injector issues",
            "Vacuum leak",
        ],
        "severity_en": "Stop driving - schedule immediate inspection",
        "recommended_action_en": (
            "Do not continue driving; tow or drive minimally to a mechanic"
        ),
        "estimated_cost_usd_min": 100,
        "estimated_cost_usd_max": 800,
        "title_ja": "ランダム/複数シリンダーの失火検出",
        "description_ja": "エンジン制御モジュールが複数のシリンダーで失火を検出しました。",
        "likely_causes_ja": [
            "スパークプラグの不良",
            "イグニッションコイルの不良",
            "燃料インジェクターの問題",
            "真空漏れ",
        ],
        "severity_ja": "直ちに停止 - 即時点検が必要",
        "recommended_action_ja": (
            "運転を継続しないでください。整備士まで最小限の運転で移動してください"
        ),
        "estimated_cost_jpy_min": 15000,
        "estimated_cost_jpy_max": 100000,
        "embed_text": (
            "P0300 random multiple cylinder misfire spark plugs ignition coils "
            "fuel injector vacuum ミスファイア 失火 プラグ コイル"
        ),
    },
    {
        "entry_type": "obd_code",
        "obd_code": "P0420",
        "title_en": "Catalyst System Efficiency Below Threshold (Bank 1)",
        "description_en": (
            "Catalytic converter efficiency may be below threshold on bank 1."
        ),
        "likely_causes_en": [
            "Failing catalytic converter",
            "O2 sensor fault",
            "Exhaust leak",
            "Upstream misfire",
        ],
        "severity_en": "Caution - inspect soon; may fail emissions",
        "recommended_action_en": (
            "Scan freeze-frame data; check exhaust leaks and O2 sensors before "
            "replacing catalyst"
        ),
        "estimated_cost_usd_min": 200,
        "estimated_cost_usd_max": 2500,
        "title_ja": "触媒システム効率低下（バンク1）",
        "description_ja": (
            "バンク1の触媒コンバーター効率が基準を下回っている可能性があります。"
        ),
        "likely_causes_ja": [
            "触媒劣化",
            "O2センサー不良",
            "排気漏れ",
            "上流のミスファイア",
        ],
        "severity_ja": "注意 - 早めに点検。排ガス検査に影響する可能性",
        "recommended_action_ja": (
            "フリーズフレーム確認。触媒交換前に排気漏れとO2センサーを点検"
        ),
        "estimated_cost_jpy_min": 30000,
        "estimated_cost_jpy_max": 350000,
        "embed_text": (
            "P0420 catalyst efficiency bank 1 O2 sensor exhaust leak emissions "
            "触媒 排ガス"
        ),
    },
    {
        "entry_type": "symptom",
        "obd_code": None,
        "title_en": "Engine overheating with steam",
        "description_en": (
            "Temperature rises and steam or coolant smell appears from the engine bay."
        ),
        "likely_causes_en": [
            "Coolant leak",
            "Failed thermostat",
            "Water pump failure",
            "Radiator fan failure",
        ],
        "severity_en": "Stop immediately - risk of severe engine damage",
        "recommended_action_en": (
            "Pull over safely, shut off engine, do not open hot radiator cap; tow if needed"
        ),
        "estimated_cost_usd_min": 100,
        "estimated_cost_usd_max": 1500,
        "title_ja": "蒸気を伴うエンジンオーバーヒート",
        "description_ja": "水温が上昇し、エンジンルームから蒸気やクーラント臭が出る。",
        "likely_causes_ja": [
            "クーラント漏れ",
            "サーモスタット不良",
            "ウォーターポンプ故障",
            "ラジエーターファン故障",
        ],
        "severity_ja": "直ちに停止 - 重大なエンジン損傷のリスク",
        "recommended_action_ja": (
            "安全に停車しエンジン停止。熱いラジエーターキャップは開けない。必要ならレッカー"
        ),
        "estimated_cost_jpy_min": 15000,
        "estimated_cost_jpy_max": 200000,
        "embed_text": (
            "engine overheating steam coolant thermostat water pump radiator "
            "オーバーヒート 蒸気 クーラント"
        ),
    },
    {
        "entry_type": "symptom",
        "obd_code": None,
        "title_en": "Battery no-crank / click only",
        "description_en": (
            "Starter does not crank; may hear a single click. Lights may be dim."
        ),
        "likely_causes_en": [
            "Discharged battery",
            "Corroded terminals",
            "Faulty starter",
            "Alternator not charging",
        ],
        "severity_en": "Caution - vehicle may not restart",
        "recommended_action_en": "Test battery CCA and charging voltage; clean terminals",
        "estimated_cost_usd_min": 50,
        "estimated_cost_usd_max": 600,
        "title_ja": "セルが回らない・カチッという音のみ",
        "description_ja": (
            "スターターが回らず、カチッと音がするだけ。灯火が暗い場合もある。"
        ),
        "likely_causes_ja": [
            "バッテリー上がり",
            "端子腐食",
            "スターター不良",
            "オルタネーター充電不良",
        ],
        "severity_ja": "注意 - 再始動できない可能性",
        "recommended_action_ja": "バッテリーCCAと充電電圧を測定。端子を清掃",
        "estimated_cost_jpy_min": 8000,
        "estimated_cost_jpy_max": 80000,
        "embed_text": (
            "battery no crank click starter alternator terminals "
            "バッテリー セル カチッ"
        ),
    },
    {
        "entry_type": "general_repair",
        "obd_code": None,
        "title_en": "Brake pedal sinks to floor",
        "description_en": (
            "Brake pedal travels unusually far or sinks toward the floor under pressure."
        ),
        "likely_causes_en": [
            "Brake fluid leak",
            "Master cylinder failure",
            "Air in brake lines",
        ],
        "severity_en": "Stop immediately - do not continue driving",
        "recommended_action_en": (
            "Stop in a safe place; use hazards; arrange tow. Do not drive."
        ),
        "estimated_cost_usd_min": 200,
        "estimated_cost_usd_max": 1200,
        "title_ja": "ブレーキペダルが床まで沈む",
        "description_ja": (
            "ブレーキペダルの踏みしろが異常に大きい、または床近くまで沈む。"
        ),
        "likely_causes_ja": [
            "ブレーキフルード漏れ",
            "マスターシリンダー不良",
            "配管内エア",
        ],
        "severity_ja": "直ちに停止 - 運転を継続しないでください",
        "recommended_action_ja": "安全な場所に停車しハザード点灯。レッカーを手配",
        "estimated_cost_jpy_min": 30000,
        "estimated_cost_jpy_max": 150000,
        "embed_text": (
            "brake pedal sinks floor hydraulic fluid leak master cylinder "
            "ブレーキ ペダル 床 効かない"
        ),
    },
    {
        "entry_type": "symptom",
        "obd_code": None,
        "title_en": "AC blows warm air only",
        "description_en": (
            "Cabin air never gets cold; compressor may not engage or system is "
            "low on refrigerant."
        ),
        "likely_causes_en": [
            "Low refrigerant / leak",
            "Failed AC compressor clutch",
            "Bad pressure switch",
            "Cabin blend door actuator",
        ],
        "severity_en": "Safe to drive - comfort issue",
        "recommended_action_en": (
            "Check for compressor engagement and have system pressure tested for leaks"
        ),
        "estimated_cost_usd_min": 80,
        "estimated_cost_usd_max": 1200,
        "title_ja": "エアコンから冷たい風が出ない",
        "description_ja": (
            "車内が冷えない。コンプレッサーが作動しない、または冷媒不足の可能性。"
        ),
        "likely_causes_ja": [
            "冷媒不足・漏れ",
            "ACコンプレッサー不良",
            "プレッシャースイッチ不良",
            "内外気/温度ドア不良",
        ],
        "severity_ja": "運転可能 - 快適性の問題",
        "recommended_action_ja": "コンプレッサー作動を確認し、冷媒圧力と漏れ点検を依頼",
        "estimated_cost_jpy_min": 10000,
        "estimated_cost_jpy_max": 150000,
        "embed_text": (
            "AC air conditioning warm air not cold refrigerant compressor clutch "
            "エアコン 冷えない クーラー"
        ),
    },
    {
        "entry_type": "symptom",
        "obd_code": None,
        "title_en": "Car pulls to one side when braking",
        "description_en": (
            "Vehicle yaws left or right under braking; may feel vibration in the "
            "pedal or steering."
        ),
        "likely_causes_en": [
            "Uneven pad wear",
            "Stuck caliper slide pin",
            "Collapsed brake hose",
            "Warped rotor one side",
        ],
        "severity_en": "Caution - inspect soon; may reduce stopping performance",
        "recommended_action_en": (
            "Do not delay brake inspection; check pad thickness and caliper free movement"
        ),
        "estimated_cost_usd_min": 120,
        "estimated_cost_usd_max": 500,
        "title_ja": "ブレーキ時に車が片側へ流れる",
        "description_ja": (
            "制動時に左右どちらかへ車が流れる。ペダルやステアに振動が出ることもある。"
        ),
        "likely_causes_ja": [
            "パッド片減り",
            "キャリパー固着",
            "ブレーキホース潰れ",
            "片側ローター歪み",
        ],
        "severity_ja": "注意 - 早めに点検。制動力低下の恐れ",
        "recommended_action_ja": "ブレーキ点検を優先。パッド厚とキャリパー作動を確認",
        "estimated_cost_jpy_min": 15000,
        "estimated_cost_jpy_max": 70000,
        "embed_text": (
            "pulls to one side braking uneven pads stuck caliper hose rotor "
            "ブレーキ 片流れ 片減り"
        ),
    },
    {
        "entry_type": "obd_code",
        "obd_code": "P0171",
        "title_en": "System Too Lean (Bank 1)",
        "description_en": "ECM reports air-fuel mixture leaner than expected on bank 1.",
        "likely_causes_en": [
            "Vacuum leak",
            "MAF sensor dirty/failing",
            "Weak fuel pump or clogged filter",
            "O2 sensor fault",
        ],
        "severity_en": "Caution - can cause misfire or catalytic damage if ignored",
        "recommended_action_en": (
            "Smoke-test for vacuum leaks; inspect MAF and fuel pressure before "
            "replacing sensors"
        ),
        "estimated_cost_usd_min": 80,
        "estimated_cost_usd_max": 900,
        "title_ja": "システムがリーンすぎる（バンク1）",
        "description_ja": "バンク1の空燃比が基準より薄いとECMが判断している。",
        "likely_causes_ja": [
            "真空漏れ",
            "MAFセンサー汚れ・不良",
            "燃料ポンプ弱い/フィルタ詰まり",
            "O2センサー不良",
        ],
        "severity_ja": "注意 - 放置すると失火や触媒損傷の恐れ",
        "recommended_action_ja": (
            "真空漏れのスモークテスト、MAFと燃圧確認をセンサー交換より先に"
        ),
        "estimated_cost_jpy_min": 10000,
        "estimated_cost_jpy_max": 120000,
        "embed_text": (
            "P0171 system too lean bank 1 vacuum MAF fuel pump O2 "
            "リーン 空燃比 負圧"
        ),
    },
    {
        "entry_type": "symptom",
        "obd_code": None,
        "title_en": "Transmission slips or delayed engagement",
        "description_en": (
            "RPM rises without matching acceleration, or long pause when shifting "
            "into Drive/Reverse."
        ),
        "likely_causes_en": [
            "Low/dirty ATF",
            "Worn clutch packs",
            "Failing solenoid",
            "Torque converter issues",
        ],
        "severity_en": "Caution - risk of stranding; avoid hard acceleration",
        "recommended_action_en": (
            "Check ATF level/condition; scan for transmission codes; limit driving "
            "until inspected"
        ),
        "estimated_cost_usd_min": 150,
        "estimated_cost_usd_max": 3500,
        "title_ja": "ミッションが滑る・ギア入りが遅い",
        "description_ja": (
            "回転だけ上がって加速しない、またはD/Rに入れても噛み込みが遅い。"
        ),
        "likely_causes_ja": [
            "ATF不足・劣化",
            "クラッチ摩耗",
            "ソレノイド不良",
            "トルコン不良",
        ],
        "severity_ja": "注意 - 走行不能のリスク。急加速を避ける",
        "recommended_action_ja": (
            "ATF量と状態を確認し、ミッション系コードをスキャン。点検まで控えめに走行"
        ),
        "estimated_cost_jpy_min": 20000,
        "estimated_cost_jpy_max": 450000,
        "embed_text": (
            "transmission slip delayed engagement ATF solenoid torque converter "
            "ミッション 滑る ギア"
        ),
    },
]

# Expected top-1 title_en substring (bilingual queries still match EN titles)
TEST_QUERIES: list[tuple[str, str]] = [
    ("My car makes a squeaking grinding noise when I brake", "Grinding noise"),
    ("brakes grinding", "Grinding noise"),
    ("engine is overheating steam coming out", "overheating"),
    ("P0300 misfire rough idle", "Misfire"),
    ("AC not cold only warm air", "AC blows"),
    ("car pulls left when braking", "pulls to one side"),
    ("P0171 lean code", "Too Lean"),
    ("transmission slips when accelerating", "Transmission slips"),
    # JP query → EN title via shared embedding space
    ("バッテリーが上がってセルが回らない", "Battery no-crank"),
]


def require_db() -> str:
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url.startswith("postgres"):
        raise SystemExit("DATABASE_URL must be set to a postgres:// connection string")
    return url


def print_status(cur) -> tuple[int, int]:
    cur.execute("select count(*), count(embedding) from knowledge_entries")
    total, emb = cur.fetchone()
    print(f"knowledge_entries: rows={total} with_embedding={emb}")
    return int(total), int(emb)


def upsert_documents(cur, docs: list[dict[str, Any]]) -> tuple[int, int]:
    """Insert by title_en if missing. Returns (inserted, skipped)."""
    inserted = skipped = 0
    for doc in docs:
        cur.execute(
            "select id from knowledge_entries where title_en = %s limit 1",
            (doc["title_en"],),
        )
        if cur.fetchone():
            skipped += 1
            continue
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
              %s, %s,
              %s, %s, %s,
              %s, %s,
              %s, %s,
              %s, %s, %s,
              %s, %s,
              %s, %s,
              %s, %s
            )
            """,
            (
                doc["entry_type"],
                doc["obd_code"],
                doc["title_en"],
                doc["description_en"],
                doc["likely_causes_en"],
                doc["severity_en"],
                doc["recommended_action_en"],
                doc["estimated_cost_usd_min"],
                doc["estimated_cost_usd_max"],
                doc["title_ja"],
                doc["description_ja"],
                doc["likely_causes_ja"],
                doc["severity_ja"],
                doc["recommended_action_ja"],
                doc["estimated_cost_jpy_min"],
                doc["estimated_cost_jpy_max"],
                doc.get("embed_text"),
                "poc_seed",
            ),
        )
        inserted += 1
        print(f"  + inserted: {doc['title_en']}")
    return inserted, skipped


def embed_missing(cur, *, force: bool) -> tuple[int, int]:
    cur.execute(
        """
        select id, entry_type, obd_code, title_en, description_en,
               likely_causes_en, severity_en, recommended_action_en,
               title_ja, description_ja, likely_causes_ja,
               severity_ja, recommended_action_ja, embed_text, embedding
        from knowledge_entries
        order by created_at
        """
    )
    cols = [d.name for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    if not force:
        rows = [r for r in rows if r.get("embedding") is None]

    print(f"Embedding {len(rows)} row(s) (force={force}, dims={EXPECTED_DIMS})")
    if not rows:
        return 0, 0

    updated = errors = 0
    batch_size = 16
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        texts = [build_embed_text(r) for r in batch]
        try:
            vectors = embed_texts_sync(texts)
        except Exception as exc:
            print(f"  embed batch failed: {exc}")
            errors += len(batch)
            continue
        for row, text, vec in zip(batch, texts, vectors):
            try:
                cur.execute(
                    """
                    update knowledge_entries
                    set embedding = %s::vector,
                        embed_text = %s,
                        updated_at = now()
                    where id = %s
                    """,
                    (vec, text, row["id"]),
                )
                updated += 1
                print(f"  OK embed {str(row['id'])[:8]}… {row['title_en'][:48]}")
            except Exception as exc:
                errors += 1
                print(f"  FAIL {row['id']}: {exc}")
        time.sleep(0.1)
    return updated, errors


def run_retrieval_tests(cur, threshold: float = 0.30, top_k: int = 3) -> int:
    """Return number of failed expectation checks."""
    print(f"\n=== Retrieval smoke tests (threshold={threshold}, top_k={top_k}) ===")
    failed = 0
    for query, expect_substr in TEST_QUERIES:
        try:
            vec = embed_texts_sync([query])[0]
        except Exception as exc:
            print(f"FAIL embed query {query!r}: {exc}")
            failed += 1
            continue

        cur.execute(
            """
            select title_en, entry_type, obd_code, similarity,
                   estimated_cost_usd_min, estimated_cost_usd_max,
                   likely_causes_en
            from match_knowledge_entries(%s::vector, %s, %s)
            """,
            (vec, threshold, top_k),
        )
        hits = cur.fetchall()
        if not hits:
            print(f"FAIL  q={query!r} → no hits")
            failed += 1
            continue

        top_title = hits[0][0] or ""
        ok = expect_substr.lower() in top_title.lower()
        # Japanese query may match title_ja path via embed_text; accept if any hit matches
        if not ok:
            ok = any(expect_substr.lower() in (h[0] or "").lower() for h in hits)

        mark = "OK  " if ok else "WEAK"
        if not ok:
            failed += 1
        print(f"{mark} q={query!r}")
        for i, h in enumerate(hits, 1):
            causes = h[6] if h[6] else []
            cause_s = ", ".join(causes[:3]) if isinstance(causes, list) else str(causes)
            print(
                f"       {i}. sim={float(h[3]):.3f} | {h[1]} {h[2] or ''} | {h[0]}\n"
                f"          cost USD {h[4]}-{h[5]} | causes: {cause_s}"
            )
        if not ok:
            print(f"       expected title containing {expect_substr!r}")
    print(f"\nRetrieval: {len(TEST_QUERIES) - failed}/{len(TEST_QUERIES)} queries met expectations")
    return failed


def main() -> int:
    parser = argparse.ArgumentParser(description="RAG knowledge PoC ingest + verify")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--test-only", action="store_true")
    parser.add_argument("--force-embed", action="store_true")
    parser.add_argument("--threshold", type=float, default=0.30)
    args = parser.parse_args()

    from app.config import get_settings

    settings = get_settings()
    url = require_db()

    if not args.status and not settings.openai_configured:
        raise SystemExit("OPENAI_API_KEY required for embed/test")

    with psycopg.connect(url, connect_timeout=30) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            print_status(cur)
            if args.status:
                return 0

            if not args.test_only:
                print("\n=== Upsert PoC documents ===")
                ins, skip = upsert_documents(cur, POC_DOCUMENTS)
                print(f"inserted={ins} already_present={skip}")

                print("\n=== Embed ===")
                upd, err = embed_missing(cur, force=args.force_embed)
                print(f"embedded={upd} errors={err}")
                print_status(cur)

            fails = run_retrieval_tests(cur, threshold=args.threshold)
            return 0 if fails == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
