"""LLM client abstraction: OpenAI, Gemini, or mock mode."""

from __future__ import annotations

import json
import re
from typing import Any

from app.config import get_settings
from app.tools.schemas import OPENAI_TOOLS


async def chat_with_tools(
    *,
    system_prompt: str,
    messages: list[dict[str, str]],
    language: str,
) -> dict[str, Any]:
    """
    Returns:
      {
        "content": str | None,
        "tool_calls": [{"name": str, "arguments": dict}],
        "provider": str,
      }
    """
    settings = get_settings()

    if settings.use_mock_llm or (
        settings.llm_provider == "openai" and not settings.openai_configured
    ) or (
        settings.llm_provider == "gemini" and not settings.gemini_configured
        and settings.llm_provider != "openai"
    ):
        # If openai not configured and provider is openai → mock
        if settings.use_mock_llm or not (
            (settings.llm_provider == "openai" and settings.openai_configured)
            or (settings.llm_provider == "gemini" and settings.gemini_configured)
        ):
            return await _mock_llm(messages, language)

    if settings.llm_provider == "gemini" and settings.gemini_configured:
        return await _gemini_chat(system_prompt, messages)
    if settings.openai_configured:
        return await _openai_chat(system_prompt, messages)
    if settings.gemini_configured:
        return await _gemini_chat(system_prompt, messages)
    return await _mock_llm(messages, language)


async def _openai_chat(system_prompt: str, messages: list[dict[str, str]]) -> dict[str, Any]:
    from openai import AsyncOpenAI

    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    oai_messages = [{"role": "system", "content": system_prompt}]
    for m in messages:
        if m["role"] in ("user", "assistant", "system"):
            oai_messages.append({"role": m["role"], "content": m["content"]})

    resp = await client.chat.completions.create(
        model=settings.openai_model,
        messages=oai_messages,
        tools=OPENAI_TOOLS,
        tool_choice="auto",
        temperature=0.4,
    )
    choice = resp.choices[0].message
    tool_calls = []
    if choice.tool_calls:
        for tc in choice.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls.append({"name": tc.function.name, "arguments": args})
    return {
        "content": choice.content,
        "tool_calls": tool_calls,
        "provider": "openai",
    }


async def _gemini_chat(system_prompt: str, messages: list[dict[str, str]]) -> dict[str, Any]:
    """Basic Gemini path; tool calling support varies by model/SDK version."""
    import google.generativeai as genai

    settings = get_settings()
    genai.configure(api_key=settings.gemini_api_key)

    # Flatten conversation for Gemini
    history_text = []
    for m in messages:
        history_text.append(f"{m['role'].upper()}: {m['content']}")
    prompt = (
        system_prompt
        + "\n\n---\nConversation:\n"
        + "\n".join(history_text)
        + "\n\nIf ready to diagnose, respond with a JSON object ONLY in this shape:\n"
        + '{"tool":"emit_diagnosis","arguments":{...diagnosis fields...}}\n'
        + "Otherwise reply with plain assistant text (one clarifying question)."
    )

    model = genai.GenerativeModel(settings.gemini_model)
    resp = await model.generate_content_async(prompt)
    text = (resp.text or "").strip()

    # Try parse tool JSON
    tool_calls = []
    content = text
    try:
        # extract JSON block if present
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            obj = json.loads(m.group(0))
            if obj.get("tool") == "emit_diagnosis" and isinstance(obj.get("arguments"), dict):
                tool_calls.append({"name": "emit_diagnosis", "arguments": obj["arguments"]})
                content = None
            elif "diagnosis" in obj and "severity_code" in obj:
                tool_calls.append({"name": "emit_diagnosis", "arguments": obj})
                content = None
    except json.JSONDecodeError:
        pass

    return {"content": content, "tool_calls": tool_calls, "provider": "gemini"}


async def _mock_llm(messages: list[dict[str, str]], language: str) -> dict[str, Any]:
    """Deterministic demo flow without API keys — for local UI testing."""
    user_msgs = [m["content"] for m in messages if m["role"] == "user"]
    n = len(user_msgs)
    last = user_msgs[-1] if user_msgs else ""

    # Detect VIN-like
    vin_match = re.search(r"\b[A-HJ-NPR-Z0-9]{17}\b", last.upper())

    if language == "ja":
        if n <= 1 and vin_match:
            return {
                "content": "VINを受け取りました。車の状態を教えてください（音・振動・警告灯など）。",
                "tool_calls": [],
                "provider": "mock",
            }
        if n <= 1:
            return {
                "content": (
                    "QT Drive Innovations 診断アシスタントです。"
                    "任意で17桁のVIN、または年式・メーカー・車種を教えてください。"
                    "もしくは、今起きている症状を教えてください。"
                ),
                "tool_calls": [],
                "provider": "mock",
            }
        if n == 2:
            return {
                "content": "その症状は、主にブレーキ時、加速時、旋回時、それとも常時のどれに近いですか？",
                "tool_calls": [],
                "provider": "mock",
            }
        if n == 3:
            return {
                "content": "警告灯は点灯していますか？また、症状はいつ頃からですか？",
                "tool_calls": [],
                "provider": "mock",
            }
        # Diagnosis
        args = {
            "language": "ja",
            "diagnosis": [
                {
                    "cause": "ブレーキパッドの摩耗（金属接触の可能性）",
                    "confidence": 75,
                    "rationale": "ブレーキ関連の症状と会話の流れからの推定（モック）。",
                },
                {
                    "cause": "ブレーキローターの摩耗・傷",
                    "confidence": 40,
                    "rationale": "異音を伴う制動症状で併発しやすい。",
                },
            ],
            "severity": "注意 - 1〜2週間以内に点検してください",
            "severity_code": "caution",
            "estimated_cost": "20,000〜60,000円",
            "currency": "JPY",
            "cost_min": 20000,
            "cost_max": 60000,
            "next_action": "整備工場でブレーキ点検を予約し、パッドとローターの測定を依頼してください。",
            "related_obd_codes": [],
            "questions_asked_count": max(0, n - 1),
            "confidence_overall": 70,
            "assumptions": ["モックLLMによるデモ診断"],
            "safety_flags": ["brakes"],
            "disclaimer": (
                "本結果は情報提供を目的としたAIによる推定であり、専門整備の代替ではありません。"
                "QT Drive Innovations / Qualitex Trading LLC は診断や修理費用の正確性を保証しません。"
            ),
        }
        return {
            "content": (
                "これまでの情報から、ブレーキ周りの摩耗が疑われます。"
                "重大度は「注意」です。早めに整備士へご相談ください。"
            ),
            "tool_calls": [{"name": "emit_diagnosis", "arguments": args}],
            "provider": "mock",
        }

    # English mock
    if n <= 1 and vin_match:
        return {
            "content": "Thanks — I’ve noted your VIN. What’s happening with the car?",
            "tool_calls": [],
            "provider": "mock",
        }
    if n <= 1:
        return {
            "content": (
                "Welcome to QT Drive Innovations. I can help estimate what may be going on. "
                "Optional: share a 17-character VIN or year/make/model — or describe the symptom."
            ),
            "tool_calls": [],
            "provider": "mock",
        }
    if n == 2:
        return {
            "content": (
                "When does it happen most: while braking, accelerating, turning, or constantly?"
            ),
            "tool_calls": [],
            "provider": "mock",
        }
    if n == 3:
        return {
            "content": "Any warning lights, and how long has this been going on?",
            "tool_calls": [],
            "provider": "mock",
        }

    args = {
        "language": "en",
        "diagnosis": [
            {
                "cause": "Worn brake pads (possible metal-to-rotor contact)",
                "confidence": 75,
                "rationale": "Mock estimate based on braking-related conversation flow.",
            },
            {
                "cause": "Worn or scored brake rotors",
                "confidence": 40,
                "rationale": "Often accompanies pad wear when noise is present.",
            },
        ],
        "severity": "Caution - inspect within 1–2 weeks",
        "severity_code": "caution",
        "estimated_cost": "150-450 USD",
        "currency": "USD",
        "cost_min": 150,
        "cost_max": 450,
        "next_action": "Schedule a brake inspection; request pad/rotor measurement.",
        "related_obd_codes": [],
        "questions_asked_count": max(0, n - 1),
        "confidence_overall": 70,
        "assumptions": ["Mock LLM demo diagnosis"],
        "safety_flags": ["brakes"],
        "disclaimer": (
            "This is an AI-assisted estimate for informational purposes only, not a substitute "
            "for professional inspection. QT Drive Innovations / Qualitex Trading LLC does not "
            "guarantee accuracy of diagnosis or repair costs."
        ),
    }
    return {
        "content": (
            "Based on what you’ve shared, brake wear is the leading possibility. "
            "Severity is Caution — have a mechanic inspect soon."
        ),
        "tool_calls": [{"name": "emit_diagnosis", "arguments": args}],
        "provider": "mock",
    }
