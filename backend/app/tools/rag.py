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
        "recommended_action_en": "Visit mechanic for brake inspection",
        "recommended_action_ja": "ブレーキ点検のため整備士に相談してください",
    },
    {
        "obd_code": None,
        "entry_type": "symptom",
        "title_en": "AC blows warm air only",
        "title_ja": "エアコンから冷たい風が出ない",
        "description_en": "Cabin air never gets cold; compressor may not engage.",
        "description_ja": "車内が冷えない。コンプレッサーが作動しない可能性。",
        "likely_causes_en": [
            "Low refrigerant / leak",
            "Failed AC compressor clutch",
            "Bad pressure switch",
        ],
        "likely_causes_ja": ["冷媒不足・漏れ", "ACコンプレッサー不良", "プレッシャースイッチ不良"],
        "severity_en": "Safe to drive - comfort issue",
        "severity_ja": "運転可能 - 快適性の問題",
        "estimated_cost_usd_min": 80,
        "estimated_cost_usd_max": 1200,
        "estimated_cost_jpy_min": 10000,
        "estimated_cost_jpy_max": 150000,
        "tags": ["ac", "air conditioning", "warm", "エアコン", "冷えない"],
        "recommended_action_en": "Have AC system pressure tested for leaks",
        "recommended_action_ja": "冷媒圧力と漏れ点検を依頼",
    },
    {
        "obd_code": None,
        "entry_type": "symptom",
        "title_en": "Car pulls to one side when braking",
        "title_ja": "ブレーキ時に車が片側へ流れる",
        "description_en": "Vehicle yaws left or right under braking.",
        "description_ja": "制動時に左右どちらかへ車が流れる。",
        "likely_causes_en": ["Uneven pad wear", "Stuck caliper slide pin", "Collapsed brake hose"],
        "likely_causes_ja": ["パッド片減り", "キャリパー固着", "ブレーキホース潰れ"],
        "severity_en": "Caution - inspect soon",
        "severity_ja": "注意 - 早めに点検",
        "estimated_cost_usd_min": 120,
        "estimated_cost_usd_max": 500,
        "estimated_cost_jpy_min": 15000,
        "estimated_cost_jpy_max": 70000,
        "tags": ["pulls", "braking", "caliper", "片流れ", "ブレーキ"],
        "recommended_action_en": "Brake inspection for pad wear and caliper free movement",
        "recommended_action_ja": "パッド厚とキャリパー作動の点検",
    },
    {
        "obd_code": "P0171",
        "entry_type": "obd_code",
        "title_en": "System Too Lean (Bank 1)",
        "title_ja": "システムがリーンすぎる（バンク1）",
        "description_en": "ECM reports air-fuel mixture leaner than expected on bank 1.",
        "description_ja": "バンク1の空燃比が基準より薄いとECMが判断している。",
        "likely_causes_en": ["Vacuum leak", "MAF sensor dirty/failing", "Weak fuel pump"],
        "likely_causes_ja": ["真空漏れ", "MAFセンサー汚れ・不良", "燃料ポンプ弱い"],
        "severity_en": "Caution - can cause misfire if ignored",
        "severity_ja": "注意 - 放置すると失火の恐れ",
        "estimated_cost_usd_min": 80,
        "estimated_cost_usd_max": 900,
        "estimated_cost_jpy_min": 10000,
        "estimated_cost_jpy_max": 120000,
        "tags": ["P0171", "lean", "vacuum", "MAF", "リーン", "空燃比"],
        "recommended_action_en": "Smoke-test vacuum leaks; inspect MAF and fuel pressure",
        "recommended_action_ja": "真空漏れのスモークテスト、MAFと燃圧確認",
    },
    {
        "obd_code": None,
        "entry_type": "symptom",
        "title_en": "Transmission slips or delayed engagement",
        "title_ja": "ミッションが滑る・ギア入りが遅い",
        "description_en": "RPM rises without matching acceleration, or delayed Drive engagement.",
        "description_ja": "回転だけ上がって加速しない、またはD入りが遅い。",
        "likely_causes_en": ["Low/dirty ATF", "Worn clutch packs", "Failing solenoid"],
        "likely_causes_ja": ["ATF不足・劣化", "クラッチ摩耗", "ソレノイド不良"],
        "severity_en": "Caution - risk of stranding",
        "severity_ja": "注意 - 走行不能のリスク",
        "estimated_cost_usd_min": 150,
        "estimated_cost_usd_max": 3500,
        "estimated_cost_jpy_min": 20000,
        "estimated_cost_jpy_max": 450000,
        "tags": ["transmission", "slip", "ATF", "ミッション", "滑る"],
        "recommended_action_en": "Check ATF level; scan transmission codes",
        "recommended_action_ja": "ATF確認とミッション系コードスキャン",
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


# Default strong-match floor (overridden by settings.rag_min_similarity in callers).
DEFAULT_MIN_SIMILARITY = 0.55


def hit_similarity(hit: dict[str, Any]) -> float | None:
    sim = hit.get("similarity")
    if isinstance(sim, (int, float)):
        return float(sim)
    return None


def is_strong_hit(hit: dict[str, Any], min_similarity: float = DEFAULT_MIN_SIMILARITY) -> bool:
    """
    Strong enough to ground the answer (causes + hard-quoted cost).

    - Exact OBD code hits (*_code sources) always count as strong.
    - Vector hits need similarity >= min_similarity.
    - Pure text-token fallbacks without a similarity score are NOT strong
      (avoid forcing weak "grounded" matches).
    """
    source = str(hit.get("source") or "")
    if "code" in source:
        return True
    sim = hit_similarity(hit)
    if sim is None:
        return False
    return sim >= min_similarity


def filter_strong_hits(
    hits: list[dict[str, Any]],
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
) -> list[dict[str, Any]]:
    return [h for h in hits if is_strong_hit(h, min_similarity)]


def format_grounded_cost(hit: dict[str, Any], language: str) -> dict[str, Any] | None:
    """
    Build hard cost fields from a knowledge hit.
    Returns None if the hit has no usable min/max for the session language.
    """
    if language == "ja":
        lo, hi = (hit.get("cost_jpy") or [None, None])[:2]
        if lo is None or hi is None:
            lo, hi = (hit.get("cost_usd") or [None, None])[:2]
            if lo is None or hi is None:
                return None
            return {
                "currency": "USD",
                "cost_min": float(lo),
                "cost_max": float(hi),
                "estimated_cost": f"{int(lo)}-{int(hi)} USD",
            }
        return {
            "currency": "JPY",
            "cost_min": float(lo),
            "cost_max": float(hi),
            "estimated_cost": f"{int(lo)}〜{int(hi)}円",
        }

    lo, hi = (hit.get("cost_usd") or [None, None])[:2]
    if lo is None or hi is None:
        return None
    return {
        "currency": "USD",
        "cost_min": float(lo),
        "cost_max": float(hi),
        "estimated_cost": f"{int(lo)}-{int(hi)} USD",
    }


def apply_grounded_cost(
    diagnosis_args: dict[str, Any],
    strong_hits: list[dict[str, Any]],
    language: str,
) -> dict[str, Any]:
    """
    Overwrite estimated_cost / currency / cost_min / cost_max from the top
    strong knowledge hit. Server-side enforcement — do not trust the LLM range.
    """
    if not strong_hits:
        return diagnosis_args
    cost = format_grounded_cost(strong_hits[0], language)
    if not cost:
        return diagnosis_args
    out = dict(diagnosis_args)
    out["estimated_cost"] = cost["estimated_cost"]
    out["currency"] = cost["currency"]
    out["cost_min"] = cost["cost_min"]
    out["cost_max"] = cost["cost_max"]
    return out


def hits_to_prompt_snippets(hits: list[dict[str, Any]]) -> list[str]:
    """Format retrieval hits as concise grounding lines for the system prompt."""
    snippets = []
    for i, h in enumerate(hits, 1):
        code = h.get("code") or h.get("entry_type") or "knowledge"
        sim = h.get("similarity")
        sim_s = f" similarity={sim:.3f}" if isinstance(sim, (int, float)) else ""
        causes = h.get("causes") or []
        if isinstance(causes, list):
            causes_s = "; ".join(str(c) for c in causes[:5])
        else:
            causes_s = str(causes)
        usd = h.get("cost_usd") or [None, None]
        jpy = h.get("cost_jpy") or [None, None]
        snippets.append(
            f"[{i}] {code}{sim_s} | severity={h.get('severity')} | "
            f"{h.get('title')} — {h.get('summary')} | "
            f"likely_causes=[{causes_s}] | "
            f"QUOTE_COST_USD={usd[0]}-{usd[1]} QUOTE_COST_JPY={jpy[0]}-{jpy[1]} | "
            f"next_action={h.get('next_action')} | source={h.get('source')}"
        )
    return snippets


def log_retrieval(
    *,
    session_id: str,
    query: str,
    raw_hits: list[dict[str, Any]],
    strong_hits: list[dict[str, Any]],
    min_similarity: float,
) -> None:
    """Server-side only — never shown to the user."""
    import logging

    logger = logging.getLogger("qt.rag")
    summary = [
        {
            "id": h.get("id"),
            "title": h.get("title_en") or h.get("title"),
            "sim": hit_similarity(h),
            "source": h.get("source"),
            "strong": is_strong_hit(h, min_similarity),
        }
        for h in raw_hits[:8]
    ]
    logger.info(
        "rag_retrieve session_id=%s min_sim=%.2f strong=%d/%d query=%r hits=%s",
        session_id,
        min_similarity,
        len(strong_hits),
        len(raw_hits),
        (query or "")[:200],
        summary,
    )


def _database_url() -> str | None:
    settings = get_settings()
    url = (settings.database_url or "").strip()
    if url.startswith("postgres") and not settings._is_placeholder(url):
        return url
    return None


def _search_via_database(
    query: str,
    language: str,
    obd_code: str | None,
    top_k: int,
    query_embedding: list[float] | None,
) -> list[dict[str, Any]]:
    """Direct Postgres RAG (works without Supabase service_role key)."""
    url = _database_url()
    if not url:
        return []

    try:
        import psycopg
    except ImportError:
        return []

    hits: list[dict[str, Any]] = []
    codes = extract_dtc_codes(query)
    if obd_code:
        codes.append(str(obd_code).upper())

    try:
        with psycopg.connect(url, connect_timeout=20) as conn:
            with conn.cursor() as cur:
                # 1) Exact OBD
                for code in codes:
                    cur.execute(
                        """
                        select id, entry_type, obd_code, title_en, title_ja,
                               description_en, description_ja,
                               likely_causes_en, likely_causes_ja,
                               severity_en, severity_ja,
                               recommended_action_en, recommended_action_ja,
                               estimated_cost_usd_min, estimated_cost_usd_max,
                               estimated_cost_jpy_min, estimated_cost_jpy_max
                        from knowledge_entries
                        where obd_code = %s
                        limit 3
                        """,
                        (code.upper(),),
                    )
                    cols = [d.name for d in cur.description]
                    for row in cur.fetchall():
                        d = dict(zip(cols, row))
                        d["_source"] = "postgres_code"
                        hits.append(_format_hit(d, language))

                # 2) Vector RPC
                if query_embedding and len(hits) < top_k:
                    # 0.30 threshold balances recall for small PoC KB vs noise
                    cur.execute(
                        """
                        select id, entry_type, obd_code, title_en, title_ja,
                               description_en, description_ja,
                               likely_causes_en, likely_causes_ja,
                               severity_en, severity_ja,
                               recommended_action_en, recommended_action_ja,
                               estimated_cost_usd_min, estimated_cost_usd_max,
                               estimated_cost_jpy_min, estimated_cost_jpy_max,
                               similarity
                        from match_knowledge_entries(%s::vector, %s, %s)
                        """,
                        (query_embedding, 0.30, top_k),
                    )
                    cols = [d.name for d in cur.description]
                    for row in cur.fetchall():
                        d = dict(zip(cols, row))
                        d["_source"] = "postgres_vector"
                        hits.append(_format_hit(d, language))

                # 3) Text safety net
                if len(hits) < top_k and query.strip():
                    cur.execute(
                        """
                        select id, entry_type, obd_code, title_en, title_ja,
                               description_en, description_ja,
                               likely_causes_en, likely_causes_ja,
                               severity_en, severity_ja,
                               recommended_action_en, recommended_action_ja,
                               estimated_cost_usd_min, estimated_cost_usd_max,
                               estimated_cost_jpy_min, estimated_cost_jpy_max,
                               embed_text
                        from knowledge_entries
                        limit 80
                        """
                    )
                    cols = [d.name for d in cur.description]
                    tokens = [
                        t
                        for t in re.findall(r"[\w\u3040-\u30ff\u4e00-\u9fff]+", query.lower())
                        if len(t) > 1
                    ]
                    for row in cur.fetchall():
                        d = dict(zip(cols, row))
                        blob = " ".join(
                            [
                                str(d.get("title_en") or ""),
                                str(d.get("title_ja") or ""),
                                str(d.get("description_en") or ""),
                                str(d.get("description_ja") or ""),
                                str(d.get("embed_text") or ""),
                                " ".join(d.get("likely_causes_en") or []),
                                " ".join(d.get("likely_causes_ja") or []),
                                str(d.get("obd_code") or ""),
                            ]
                        ).lower()
                        if any(tok in blob for tok in tokens):
                            d["_source"] = "postgres_text"
                            hits.append(_format_hit(d, language))
    except Exception:
        return []

    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for h in hits:
        key = f"{h.get('id') or ''}:{h.get('code')}:{h.get('title')}"
        if key not in seen:
            seen.add(key)
            unique.append(h)
    return unique[:top_k]


async def search_repair_knowledge(
    query: str,
    language: str = "en",
    filters: dict[str, Any] | None = None,
    top_k: int = 5,
    query_embedding: list[float] | None = None,
) -> list[dict[str, Any]]:
    """
    Search knowledge base.
    1) Postgres via DATABASE_URL (vector RPC + code + text) — preferred when available
    2) Supabase REST when service_role configured
    3) Local FALLBACK_KNOWLEDGE
    """
    settings = get_settings()
    filters = filters or {}
    obd_code = filters.get("obd_code")
    lang = language if language in ("en", "ja") else "en"

    # Prefer direct Postgres (works without service_role)
    pg_hits = _search_via_database(query, lang, obd_code, top_k, query_embedding)
    if pg_hits:
        return pg_hits

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
                        "match_threshold": 0.30,
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
