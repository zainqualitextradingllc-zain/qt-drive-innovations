"""Local mock-demo smoke test for EN/JA multi-turn diagnostics."""

from __future__ import annotations

import json
import sys
import urllib.request


def post_chat(message: str, language: str, session_id: str | None) -> dict:
    body = json.dumps(
        {"message": message, "language": language, "session_id": session_id}
    ).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def get(url: str) -> tuple[int, str]:
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.status, r.read().decode("utf-8", "replace")


def run_flow(language: str, messages: list[str]) -> list[dict]:
    session = None
    results: list[dict] = []
    print(f"\n=== {language.upper()} FLOW ===")
    for i, msg in enumerate(messages, 1):
        data = post_chat(msg, language, session)
        session = data["session_id"]
        results.append(data)
        reply = data.get("reply") or ""
        print(f"Turn {i}: mode={data['mode']} | {reply[:120]}")
        diag = data.get("diagnosis")
        if diag:
            print(
                f"  DIAGNOSIS severity={diag['severity_code']} "
                f"lang={diag['language']} currency={diag['currency']} "
                f"cost={diag['estimated_cost']}"
            )
            print(f"  cause0={diag['diagnosis'][0]['cause']}")
            print(f"  rag_hits={len(data.get('rag_hits') or [])}")
    return results


def main() -> int:
    # Health
    status, health_raw = get("http://127.0.0.1:8000/health")
    health = json.loads(health_raw)
    print("=== HEALTH ===")
    print(json.dumps(health, ensure_ascii=False))
    assert status == 200 and health.get("status") == "ok"

    # Frontend
    print("\n=== FRONTEND ===")
    for path in ("/en", "/ja"):
        st, html = get(f"http://localhost:3000{path}")
        ok_toggle = ("日本語" in html) and ("English" in html)
        ok_brand = "QT Drive" in html
        print(f"{path}: status={st} brand={ok_brand} lang_toggle={ok_toggle}")
        assert st == 200 and ok_toggle and ok_brand

    # Mock LLM: turns 1–3 are questions; turn 4+ emits diagnosis
    en_msgs = [
        "My brakes grind when I slow down",
        "Mostly while braking, worse at low speeds",
        "No warning lights. About two weeks, almost every stop",
        "Please give me the diagnosis",
    ]
    ja_msgs = [
        "減速するとブレーキがゴリゴリ音がします",
        "ほぼブレーキ時です。低速で目立ちます",
        "警告灯なし。2週間くらい、ほぼ毎回です",
        "診断をお願いします",
    ]

    en = run_flow("en", en_msgs)
    ja = run_flow("ja", ja_msgs)

    # Multi-turn questions before diagnosis
    assert any(r["mode"] == "question" for r in en[:-1]), "EN missing follow-up questions"
    assert any(r["mode"] == "question" for r in ja[:-1]), "JA missing follow-up questions"

    assert en[-1]["mode"] == "diagnosis" and en[-1].get("diagnosis"), "EN diagnosis missing"
    assert ja[-1]["mode"] == "diagnosis" and ja[-1].get("diagnosis"), "JA diagnosis missing"

    assert en[-1]["diagnosis"]["language"] == "en"
    assert ja[-1]["diagnosis"]["language"] == "ja"
    assert en[-1]["diagnosis"]["currency"] == "USD"
    assert ja[-1]["diagnosis"]["currency"] == "JPY"
    assert en[-1]["diagnosis"]["severity_code"] in {
        "safe_to_drive",
        "caution",
        "stop_immediately",
    }
    assert ja[-1]["diagnosis"]["severity_code"] in {
        "safe_to_drive",
        "caution",
        "stop_immediately",
    }

    print("\n=== SUCCESS CRITERIA ===")
    print("[x] Backend health check returns OK")
    print("[x] Frontend loads at localhost:3000 (/en and /ja)")
    print("[x] Chat responds to symptom input")
    print("[x] Follow-up questions appear (multi-turn works)")
    print("[x] Diagnosis card payload displays at the end")
    print("[x] Language toggle present on EN and JA pages; API language=en|ja correct")
    print("\nALL ASSERTIONS PASSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\nSMOKE TEST FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
