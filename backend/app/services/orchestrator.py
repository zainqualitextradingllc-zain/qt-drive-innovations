"""Orchestration layer — Skill #1 car diagnostics brain."""

from __future__ import annotations

import re
from typing import Any

from app.config import get_settings
from app.models.chat import ChatRequest, ChatResponse, VehicleContext
from app.models.diagnosis import DiagnosisPayload
from app.prompts.diagnostic import build_context_block, get_system_prompt
from app.services.llm import chat_with_tools
from app.services.session import SessionState, session_store
from app.tools.rag import (
    apply_grounded_cost,
    filter_strong_hits,
    format_grounded_cost,
    hits_to_prompt_snippets,
    log_retrieval,
    search_repair_knowledge,
)
from app.tools.vin import decode_vin_nhtsa, extract_vin

# Simple JP character detection for language fallback
_JP_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


def detect_message_language(text: str) -> str:
    if not text:
        return "en"
    jp = len(_JP_RE.findall(text))
    # ratio of CJK / hiragana / katakana vs latin letters
    latin = len(re.findall(r"[A-Za-z]", text))
    if jp >= 3 and jp >= latin:
        return "ja"
    return "en"


def route_intent(message: str) -> str:
    """Lightweight intent router — expandable for future skills."""
    m = message.lower()
    legal = ["trademark", "uspto", "patent", "商標", "特許", "legal"]
    business = ["analytics", "revenue", "kpi", "売上", "分析"]
    techreads = ["tech reads", "techreads", "玩具", "toys", "books"]
    if any(k in m for k in legal):
        return "trademark_legal"
    if any(k in m for k in business):
        return "business_analytics"
    if any(k in m for k in techreads):
        return "tech_reads_support"
    return "car_diagnostics"


def _vehicle_from_decode(decoded: dict[str, Any]) -> VehicleContext:
    return VehicleContext(
        vin=decoded.get("vin"),
        year=decoded.get("year"),
        make=decoded.get("make"),
        model=decoded.get("model"),
        engine=decoded.get("engine"),
        source="nhtsa_vpic",
        raw=decoded.get("raw_keys_sample"),
    )


def _count_symptom_questions(state: SessionState) -> int:
    """Count assistant turns that look like clarifying questions after first user msg."""
    return state.questions_asked_count


async def process_chat(req: ChatRequest) -> ChatResponse:
    settings = get_settings()
    state = session_store.get_or_create(req.session_id, req.language)

    if req.vehicle:
        state.vehicle = req.vehicle.model_dump()

    # Merge client history if provided and session empty
    if req.messages and not state.messages:
        state.messages = [m.model_dump() for m in req.messages]

    intent = route_intent(req.message)
    if intent != "car_diagnostics":
        if req.language == "ja":
            reply = (
                f"「{intent}」スキルは準備中です。"
                "現在は自動車診断（Skill #1）のみ利用できます。車の症状について教えてください。"
            )
        else:
            reply = (
                f"The “{intent}” skill is not active yet. "
                "Car Diagnostics (Skill #1) is available now — tell me what’s happening with your vehicle."
            )
        state.messages.append({"role": "user", "content": req.message})
        state.messages.append({"role": "assistant", "content": reply})
        session_store.save(state)
        return ChatResponse(
            session_id=state.session_id,
            language=req.language,
            reply=reply,
            mode="info",
            vehicle=VehicleContext(**state.vehicle) if state.vehicle else None,
            intent=intent,
            questions_asked_count=state.questions_asked_count,
        )

    # VIN auto-detect + decode
    vin = extract_vin(req.message)
    if vin and (not state.vehicle or state.vehicle.get("vin") != vin):
        decoded = await decode_vin_nhtsa(vin)
        if decoded.get("ok"):
            vehicle = _vehicle_from_decode(decoded)
            state.vehicle = vehicle.model_dump()

    # RAG vector query when OpenAI embeddings + Postgres/Supabase knowledge are available
    query_embedding = None
    if settings.openai_configured and (
        settings.database_configured or settings.supabase_configured
    ):
        try:
            from app.services.embeddings import embed_query

            query_embedding = await embed_query(req.message)
        except Exception:
            query_embedding = None

    raw_rag_hits = await search_repair_knowledge(
        query=req.message,
        language=req.language,
        top_k=5,
        query_embedding=query_embedding,
    )
    min_sim = float(settings.rag_min_similarity)
    # Only strong hits are shown to the model / used for hard cost quotes.
    # Weak vector hits are dropped so GPT falls back to general knowledge.
    turn_strong = filter_strong_hits(raw_rag_hits, min_similarity=min_sim)
    if turn_strong:
        state.last_strong_rag_hits = turn_strong
    # Prefer this turn's strong hits; else carry session grounding for later
    # "give me a diagnosis" turns that re-embed poorly.
    rag_hits = turn_strong or list(state.last_strong_rag_hits or [])
    log_retrieval(
        session_id=state.session_id,
        query=req.message,
        raw_hits=raw_rag_hits,
        strong_hits=turn_strong,
        min_similarity=min_sim,
    )
    snippets = hits_to_prompt_snippets(rag_hits)
    mandatory_cost = (
        format_grounded_cost(rag_hits[0], req.language) if rag_hits else None
    )

    detected = detect_message_language(req.message)
    context_block = build_context_block(
        language=req.language,
        vehicle=state.vehicle,
        questions_asked=state.questions_asked_count,
        max_questions=settings.max_clarifying_questions,
        rag_snippets=snippets,
        detected_user_language=detected,
        has_strong_grounding=bool(rag_hits),
        mandatory_cost_quote=mandatory_cost,
        min_similarity=min_sim,
    )

    system_prompt = get_system_prompt(req.language) + "\n\n" + context_block

    state.messages.append({"role": "user", "content": req.message})

    llm_result = await chat_with_tools(
        system_prompt=system_prompt,
        messages=state.messages,
        language=req.language,
    )

    diagnosis_payload: DiagnosisPayload | None = None
    reply = llm_result.get("content") or ""
    mode: str = "question"

    for tc in llm_result.get("tool_calls") or []:
        name = tc.get("name")
        args = tc.get("arguments") or {}

        if name == "decode_vin":
            vin_arg = args.get("vin") or vin
            if vin_arg:
                decoded = await decode_vin_nhtsa(vin_arg)
                if decoded.get("ok"):
                    state.vehicle = _vehicle_from_decode(decoded).model_dump()
                    if req.language == "ja":
                        reply = (
                            reply
                            or f"VINを解析しました: {decoded.get('year')} {decoded.get('make')} {decoded.get('model')}。症状を教えてください。"
                        )
                    else:
                        reply = (
                            reply
                            or f"VIN decoded: {decoded.get('year')} {decoded.get('make')} {decoded.get('model')}. What’s happening with the car?"
                        )
                    mode = "question"

        elif name == "search_repair_knowledge":
            extra_raw = await search_repair_knowledge(
                query=args.get("query") or req.message,
                language=args.get("language") or req.language,
                filters=args.get("filters"),
                top_k=int(args.get("top_k") or 5),
            )
            tool_strong = filter_strong_hits(extra_raw, min_similarity=min_sim)
            if tool_strong:
                state.last_strong_rag_hits = tool_strong
                rag_hits = tool_strong
            log_retrieval(
                session_id=state.session_id,
                query=args.get("query") or req.message,
                raw_hits=extra_raw,
                strong_hits=tool_strong,
                min_similarity=min_sim,
            )
            # Continue; usually LLM already has context. Keep reply if any.

        elif name == "emit_diagnosis":
            # Enrich vehicle_context from session if missing
            if state.vehicle and not args.get("vehicle_context"):
                args["vehicle_context"] = {
                    "vin": state.vehicle.get("vin"),
                    "year": state.vehicle.get("year"),
                    "make": state.vehicle.get("make"),
                    "model": state.vehicle.get("model"),
                    "engine": state.vehicle.get("engine"),
                    "source": state.vehicle.get("source") or "unknown",
                }
            if "questions_asked_count" not in args:
                args["questions_asked_count"] = state.questions_asked_count
            # Hard-quote cost from top strong RAG hit (this turn or session carry-over)
            cost_hits = rag_hits or list(state.last_strong_rag_hits or [])
            args = apply_grounded_cost(args, cost_hits, req.language)
            try:
                diagnosis_payload = DiagnosisPayload.model_validate(args)
                mode = "diagnosis"
                if not reply:
                    reply = (
                        diagnosis_payload.next_action
                        if req.language == "en"
                        else diagnosis_payload.next_action
                    )
            except Exception as exc:
                mode = "error"
                reply = (
                    f"Diagnosis formatting error: {exc}"
                    if req.language == "en"
                    else f"診断データの形式エラー: {exc}"
                )

        elif name == "route_intent":
            intent = args.get("intent") or intent

    if not reply:
        reply = (
            "Could you share a bit more detail about the symptom?"
            if req.language == "en"
            else "症状について、もう少し詳しく教えてください。"
        )

    # Increment clarifying question count on question-mode assistant turns
    # (exclude pure VIN-only first turns loosely — still OK for MVP)
    if mode == "question":
        # Count user messages that look like symptoms (not pure VIN)
        if not (vin and len(req.message.strip()) <= 20):
            state.questions_asked_count = _count_symptom_questions(state) + 1

    state.messages.append({"role": "assistant", "content": reply})
    # Cap history
    if len(state.messages) > 40:
        state.messages = state.messages[-40:]
    session_store.save(state)

    # Phase 4a.0: integrity hash (fail-safe — never break diagnosis / lead flow)
    content_hash: str | None = None
    diagnosis_id: str | None = None
    if mode == "diagnosis" and diagnosis_payload is not None:
        try:
            from app.services.attestation import create_diagnosis_attestation

            att = create_diagnosis_attestation(
                session_id=state.session_id,
                diagnosis=diagnosis_payload,
                locale=req.language,
                # Session vehicle is what the UI shows; LLM vehicle_context is often empty
                vehicle_fallback=state.vehicle,
            )
            if att:
                content_hash = att.get("content_hash")
                diagnosis_id = att.get("diagnosis_id")
        except Exception:
            # Extra belt-and-suspenders; create_diagnosis_attestation already catches
            import logging

            logging.getLogger(__name__).exception(
                "attestation hook failed session=%s", state.session_id
            )

    return ChatResponse(
        session_id=state.session_id,
        language=req.language,
        reply=reply,
        mode=mode,  # type: ignore[arg-type]
        vehicle=VehicleContext(**state.vehicle) if state.vehicle else None,
        diagnosis=diagnosis_payload,
        questions_asked_count=state.questions_asked_count,
        intent=intent,
        rag_hits=rag_hits,
        content_hash=content_hash,
        diagnosis_id=diagnosis_id,
    )
