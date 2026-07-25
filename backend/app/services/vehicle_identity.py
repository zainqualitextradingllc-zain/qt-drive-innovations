"""Detect real vehicle identity vs LLM/session placeholders."""

from __future__ import annotations

from typing import Any

# LLM often emits these instead of null when the user skipped vehicle details.
_PLACEHOLDER_STRINGS = frozenset(
    {
        "",
        "unknown",
        "n/a",
        "na",
        "none",
        "null",
        "undefined",
        "not specified",
        "not provided",
        "not known",
        "unspecified",
        "any",
        "any car",
        "generic",
        "n/a n/a",
        "不明",
        "なし",
        "未設定",
        "わからない",
        "分かりません",
        "わからないです",
        "不明です",
    }
)


def _as_dict(vehicle: Any) -> dict[str, Any] | None:
    if vehicle is None:
        return None
    if isinstance(vehicle, dict):
        return vehicle
    if hasattr(vehicle, "model_dump"):
        return vehicle.model_dump()
    return None


def is_real_vehicle_string(value: Any) -> bool:
    if value is None:
        return False
    s = str(value).strip()
    if not s:
        return False
    return s.lower() not in _PLACEHOLDER_STRINGS


def is_real_vehicle_year(value: Any) -> bool:
    if value is None or value is False:
        return False
    try:
        y = int(value)
    except (TypeError, ValueError):
        return False
    # 0 / negative / tiny numbers are placeholders, not model years
    return 1980 <= y <= 2100


def has_vehicle_identity(vehicle: Any) -> bool:
    """
    True only when make/model/year/VIN look like real user or VIN-decode data.
    Treats year=0 and make/model='unknown' as NO identity.
    """
    v = _as_dict(vehicle)
    if not v:
        return False
    return bool(
        is_real_vehicle_string(v.get("make"))
        or is_real_vehicle_string(v.get("model"))
        or is_real_vehicle_year(v.get("year"))
        or is_real_vehicle_string(v.get("vin"))
    )


def sanitize_vehicle_fields(vehicle: Any) -> dict[str, Any]:
    """
    Return year/make/model/engine with placeholders coerced to null.
    Never includes VIN (PII). Used for attestations and display hygiene.
    """
    out: dict[str, Any] = {
        "engine": None,
        "make": None,
        "model": None,
        "year": None,
    }
    v = _as_dict(vehicle)
    if not v:
        return out

    if is_real_vehicle_year(v.get("year")):
        out["year"] = int(v["year"])
    if is_real_vehicle_string(v.get("make")):
        out["make"] = str(v["make"]).strip()
    if is_real_vehicle_string(v.get("model")):
        out["model"] = str(v["model"]).strip()
    if is_real_vehicle_string(v.get("engine")):
        out["engine"] = str(v["engine"]).strip()
    return out
