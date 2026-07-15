"""Function-calling / tool schemas for the orchestrator LLM."""

from typing import Any

EMIT_DIAGNOSIS_PARAMETERS: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "language",
        "diagnosis",
        "severity",
        "severity_code",
        "estimated_cost",
        "currency",
        "next_action",
        "disclaimer",
    ],
    "properties": {
        "language": {
            "type": "string",
            "enum": ["en", "ja"],
            "description": "Language of all human-readable fields in this payload.",
        },
        "vehicle_context": {
            "type": "object",
            "properties": {
                "vin": {"type": ["string", "null"]},
                "year": {"type": ["integer", "null"]},
                "make": {"type": ["string", "null"]},
                "model": {"type": ["string", "null"]},
                "engine": {"type": ["string", "null"]},
                "source": {
                    "type": "string",
                    "enum": ["nhtsa_vpic", "user_reported", "unknown"],
                },
            },
        },
        "diagnosis": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {
                "type": "object",
                "required": ["cause", "confidence"],
                "properties": {
                    "cause": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 100},
                    "rationale": {"type": "string"},
                },
            },
        },
        "severity": {
            "type": "string",
            "description": "Human-readable severity with short guidance, localized.",
        },
        "severity_code": {
            "type": "string",
            "enum": ["safe_to_drive", "caution", "stop_immediately"],
        },
        "estimated_cost": {
            "type": "string",
            "description": "Localized cost range, e.g. '150-400 USD' or '20,000〜60,000円'.",
        },
        "currency": {"type": "string", "enum": ["USD", "JPY"]},
        "cost_min": {"type": ["number", "null"]},
        "cost_max": {"type": ["number", "null"]},
        "next_action": {"type": "string"},
        "related_obd_codes": {
            "type": "array",
            "items": {"type": "string"},
        },
        "questions_asked_count": {"type": "integer", "minimum": 0, "maximum": 10},
        "confidence_overall": {"type": "number", "minimum": 0, "maximum": 100},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "safety_flags": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [
                    "brakes",
                    "steering",
                    "fire_fuel",
                    "overheat",
                    "airbag",
                    "loss_of_control",
                    "none",
                ],
            },
        },
        "disclaimer": {"type": "string"},
    },
}

OPENAI_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "emit_diagnosis",
            "description": (
                "Emit a structured, language-aware vehicle diagnosis when enough "
                "information has been gathered or safety requires immediate conclusion."
            ),
            "parameters": EMIT_DIAGNOSIS_PARAMETERS,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "decode_vin",
            "description": "Decode a vehicle VIN via NHTSA vPIC (free, no API key).",
            "parameters": {
                "type": "object",
                "required": ["vin"],
                "properties": {
                    "vin": {
                        "type": "string",
                        "minLength": 11,
                        "maxLength": 17,
                        "description": "17-character VIN (partial accepted by NHTSA in some cases).",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_repair_knowledge",
            "description": "RAG search over bilingual OBD-II and symptom→cause knowledge.",
            "parameters": {
                "type": "object",
                "required": ["query", "language"],
                "properties": {
                    "query": {"type": "string"},
                    "language": {"type": "string", "enum": ["en", "ja", "both"]},
                    "filters": {
                        "type": "object",
                        "properties": {
                            "obd_code": {"type": "string"},
                            "system": {
                                "type": "string",
                                "enum": [
                                    "engine",
                                    "brakes",
                                    "transmission",
                                    "electrical",
                                    "hvac",
                                    "suspension",
                                    "safety",
                                    "other",
                                ],
                            },
                            "make": {"type": "string"},
                        },
                    },
                    "top_k": {
                        "type": "integer",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 12,
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "route_intent",
            "description": "Classify user intent for multi-skill orchestration.",
            "parameters": {
                "type": "object",
                "required": ["intent", "confidence"],
                "properties": {
                    "intent": {
                        "type": "string",
                        "enum": [
                            "car_diagnostics",
                            "business_analytics",
                            "trademark_legal",
                            "tech_reads_support",
                            "smalltalk",
                            "unknown",
                        ],
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
        },
    },
]

TOOL_NAMES = {t["function"]["name"] for t in OPENAI_TOOLS}


def gemini_tool_declarations() -> list[dict[str, Any]]:
    """Flatten OpenAI-style tools for Gemini function declarations."""
    decls = []
    for tool in OPENAI_TOOLS:
        fn = tool["function"]
        decls.append(
            {
                "name": fn["name"],
                "description": fn["description"],
                "parameters": fn["parameters"],
            }
        )
    return decls
