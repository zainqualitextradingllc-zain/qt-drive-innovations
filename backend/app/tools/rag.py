"""Bilingual RAG search over Supabase pgvector knowledge_entries."""

from __future__ import annotations

import re
from typing import Any

from app.config import get_settings

DTC_PATTERN = re.compile(r"\b([PCBU][0-9A-F]{4})\b", re.IGNORECASE)

# Offline fallback when Supabase is not configured (mock demo)
FALLBACK_KNOWLEDGE: list[dict[str, Any]] = [
    {
        "obd_code": "P0300",
        "entry_type": "obd_code",
        "title_en": "Random/Multiple Cylinder Misfire Detected",
        "title_ja": "ランダム/複数シリンダーの失火検出",
        "description_en": "ECM detected misfires across multiple cylinders.",
        "description_ja": "エンジン制御モジュールが複数のシリンダーで失火を検出しました。",
        "likely_causes_en": [
            "Faulty spark plugs",
            "Bad ignition coils",
            "Fuel injector issues",
            "Vacuum leak",
        ],
        "likely_causes_ja": [
            "スパークプラグの不良",
            "イグニッションコイルの不良",
            "燃料インジェクターの問題",
            "真空漏れ",
        ],
        "severity_en": "Stop driving - schedule immediate inspection",
        "severity_ja": "直ちに停止 - 即時点検が必要",
        "estimated_cost_usd_min": 100,
        "estimated_cost_usd_max": 800,
        "estimated_cost_jpy_min": 15000,
        "estimated_cost_jpy_max": 100000,
        "tags": ["misfire", "rough idle", "ミスファイア", "失火"],
    },
    {
        "obd_code": "P0420",
        "entry_type": "obd_code",
        "title_en": "Catalyst System Efficiency Below Threshold (Bank 1)",
        "title_ja": "触媒システム効率低下（バンク1）",
        "description_en": "Catalytic converter efficiency may be reduced.",
        "description_ja": "触媒コンバーターの効率が低下している可能性があります。",
        "likely_causes_en": ["Failing catalytic converter", "O2 sensor", "Exhaust leak"],
        "likely_causes_ja": ["触媒劣化", "O2センサー", "排気漏れ"],
        "severity_en": "Caution - inspect soon",
        "severity_ja": "注意 - 早めに点検",
        "estimated_cost_usd_min": 200,
        "estimated_cost_usd_max": 2500,
        "estimated_cost_jpy_min": 30000,
        "estimated_cost_jpy_max": 350000,
        "tags": ["catalyst", "emissions", "触媒", "排ガス"],
    },
    {
        "obd_code": None,
        "entry_type": "symptom",
        "title_en": "Grinding noise when braking",
        "title_ja": "ブレーキ時にきしむ音がする",
        "description_en": "A grinding or high-pitched sound when the brake pedal is pressed.",
        "description_ja": "ブレーキペダルを踏むと高音またはこすれる音が発生する。",
        "likely_causes_en": ["Worn brake pads", "Warped rotor", "Debris stuck in caliper"],
        "likely_causes_ja": ["ブレーキパッドの摩耗", "ローターの歪み", "キャリパー内の異物"],
        "severity_en": "Caution - inspect within 1-2 weeks",
        "severity_ja": "注意 - 1〜2週間以内に点検してください",
        "estimated_cost_usd_min": 150,
        "estimated_cost_usd_max": 400,
        "estimated_cost_jpy_min": 20000,
        "estimated_cost_jpy_max": 60000,
        "tags": ["grinding", "brakes", "ブレーキ", "キーキー", "ゴリゴリ", "きしむ"],
    },
    {
        "obd_code": None,
        "entry_type": "symptom",
        "title_en": "Engine overheating with steam",
        "title_ja": "蒸気を伴うエンジンオーバーヒート",
        "description_en": "Stop driving to avoid severe engine damage.",
        "description_ja": "重大損傷防止のため運転を中止してください。",
        "likely_causes_en": ["Coolant leak", "Failed thermostat", "Water pump", "Radiator fan"],
        "likely_causes_ja": ["クーラント漏れ", "サーモスタット不良", "ウォーターポンプ", "ラジエーターファン"],
        "severity_en": "Stop immediately",
        "severity_ja": "直ちに停止",
        "estimated_cost_usd_min": 100,
        "estimated_cost_usd_max": 1500,
        "estimated_cost_jpy_min": 15000,
        "estimated_cost_jpy_max": 200000,
        "tags": ["overheat", "steam", "オーバーヒート", "蒸気", "冷却"],
    },
]


def extract_dtc_codes(text: str) -> list[str]:
    return [m.group(1).upper() for m in DTC_PATTERN.finditer(text or "")]


def _format_hit(row: dict[str, Any], language: str) -> dict[str, Any]:
    is_ja = language == "ja"
    return {
        "id": row.get("id"),
        "code": row.get("obd_code"),
        "entry_type": row.get("entry_type"),
        "title": row.get("title_ja") if is_ja else row.get("title_en"),
        "summary": row.get("description_ja") if is_ja else row.get("description_en"),
        "causes": row.get("likely_causes_ja") if is_ja else row.get("likely_causes_en"),
        "severity": row.get("severity_ja") if is_ja else row.get("severity_en"),
        "next_action": row.get("recommended_action_ja")
        if is_ja
        else row.get("recommended_action_en"),
        "title_en": row.get("title_en"),
        "title_ja": row.get("title_ja"),
        "cost_usd": [
            row.get("estimated_cost_usd_min"),
            row.get("estimated_cost_usd_max"),
        ],
        "cost_jpy": [
            row.get("estimated_cost_jpy_min"),
            row.get("estimated_cost_jpy_max"),
        ],
        "similarity": row.get("similarity"),
        "source": row.get("_source", "supabase"),
    }


def _fallback_search(
    query: str,
    language: str,
    obd_code: str | None,
    top_k: int,
) -> list[dict[str, Any]]:
    q = (query or "").lower()
    codes = extract_dtc_codes(query)
    if obd_code:
        codes.append(obd_code.upper())

    scored: list[tuple[float, dict[str, Any]]] = []
    for row in FALLBACK_KNOWLEDGE:
        score = 0.0
        if row.get("obd_code") and row["obd_code"] in codes:
            score += 10.0
        blob = " ".join(
            [
                row.get("title_en") or "",
                row.get("title_ja") or "",
                row.get("description_en") or "",
                row.get("description_ja") or "",
                " ".join(row.get("tags") or []),
                " ".join(row.get("likely_causes_en") or []),
                " ".join(row.get("likely_causes_ja") or []),
            ]
        ).lower()
        for token in re.findall(r"[\w\u3040-\u30ff\u4e00-\u9fff]+", q):
            if len(token) > 1 and token in blob:
                score += 1.0
        if score > 0:
            scored.append((score, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    hits = []
    for _, row in scored[:top_k]:
        item = dict(row)
        item["_source"] = "fallback"
        hits.append(_format_hit(item, language if language != "both" else "en"))
    return hits


def hits_to_prompt_snippets(hits: list[dict[str, Any]]) -> list[str]:
    snippets = []
    for h in hits:
        code = h.get("code") or h.get("entry_type") or "knowledge"
        sim = h.get("similarity")
        sim_s = f" sim={sim:.3f}" if isinstance(sim, (int, float)) else ""
        snippets.append(
            f"{code}{sim_s} | {h.get('severity')} | {h.get('title')} — {h.get('summary')} "
            f"| causes={h.get('causes')} | USD={h.get('cost_usd')} JPY={h.get('cost_jpy')} "
            f"| next={h.get('next_action')}"
        )
    return snippets


async def search_repair_knowledge(
    query: str,
    language: str = "en",
    filters: dict[str, Any] | None = None,
    top_k: int = 5,
    query_embedding: list[float] | None = None,
) -> list[dict[str, Any]]:
    """
    Search knowledge base.
    1) Exact OBD code match (SQL)
    2) Vector RPC match_knowledge_entries when embedding provided + Supabase configured
    3) Text contains fallback on Supabase rows
    4) Local FALLBACK_KNOWLEDGE when Supabase not configured
    """
    settings = get_settings()
    filters = filters or {}
    obd_code = filters.get("obd_code")
    lang = language if language in ("en", "ja") else "en"

    if not settings.supabase_configured:
        return _fallback_search(query, lang, obd_code, top_k)

    try:
        from supabase import create_client

        client = create_client(settings.supabase_url, settings.supabase_service_role_key)
        hits: list[dict[str, Any]] = []

        codes = extract_dtc_codes(query)
        if obd_code:
            codes.append(str(obd_code).upper())

        # 1) Exact OBD code
        for code in codes:
            resp = (
                client.table("knowledge_entries")
                .select("*")
                .eq("obd_code", code.upper())
                .limit(3)
                .execute()
            )
            for row in resp.data or []:
                row["_source"] = "supabase_code"
                hits.append(_format_hit(row, lang))

        # 2) Vector similarity via RPC (needs backfilled embeddings)
        if query_embedding and len(hits) < top_k:
            try:
                rpc = client.rpc(
                    "match_knowledge_entries",
                    {
                        "query_embedding": query_embedding,
                        "match_threshold": 0.5,
                        "match_count": top_k,
                    },
                ).execute()
                for row in rpc.data or []:
                    row["_source"] = "supabase_vector"
                    hits.append(_format_hit(row, lang))
            except Exception:
                pass

        # 3) Simple text scan (pre-embedding / hybrid safety net)
        if len(hits) < top_k and query.strip():
            resp = client.table("knowledge_entries").select("*").limit(80).execute()
            q = query.lower()
            tokens = [t for t in re.findall(r"[\w\u3040-\u30ff\u4e00-\u9fff]+", q) if len(t) > 1]
            for row in resp.data or []:
                blob = " ".join(
                    [
                        str(row.get("title_en") or ""),
                        str(row.get("title_ja") or ""),
                        str(row.get("description_en") or ""),
                        str(row.get("description_ja") or ""),
                        str(row.get("embed_text") or ""),
                        " ".join(row.get("likely_causes_en") or []),
                        " ".join(row.get("likely_causes_ja") or []),
                        str(row.get("obd_code") or ""),
                    ]
                ).lower()
                if any(tok in blob for tok in tokens):
                    row["_source"] = "supabase_text"
                    hits.append(_format_hit(row, lang))

        # Dedupe
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for h in hits:
            key = f"{h.get('id') or ''}:{h.get('code')}:{h.get('title')}"
            if key not in seen:
                seen.add(key)
                unique.append(h)

        if unique:
            return unique[:top_k]
    except Exception:
        pass

    return _fallback_search(query, lang, obd_code, top_k)
