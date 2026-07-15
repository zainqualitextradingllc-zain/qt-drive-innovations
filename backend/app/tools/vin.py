"""NHTSA vPIC VIN decode — free, no API key required."""

from __future__ import annotations

import re
from typing import Any

import httpx

NHTSA_DECODE_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin}?format=json"

VIN_PATTERN = re.compile(r"\b([A-HJ-NPR-Z0-9]{17})\b", re.IGNORECASE)


def extract_vin(text: str) -> str | None:
    if not text:
        return None
    upper = text.upper()
    match = VIN_PATTERN.search(upper)
    if match:
        return match.group(1).upper()
    cleaned = re.sub(r"[^A-HJ-NPR-Z0-9]", "", upper)
    if len(cleaned) >= 17:
        candidate = cleaned[:17]
        if re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", candidate):
            return candidate
    return None


def _pick(results: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        val = results.get(key)
        if val is not None and str(val).strip() and str(val).strip() not in ("", "0", "Not Applicable"):
            return str(val).strip()
    return None


async def decode_vin_nhtsa(vin: str) -> dict[str, Any]:
    """
    Decode VIN via NHTSA vPIC flat JSON endpoint.
    https://vpic.nhtsa.dot.gov/api/
    """
    vin = vin.strip().upper()
    if len(vin) < 11:
        return {"ok": False, "error": "VIN too short", "vin": vin}

    url = NHTSA_DECODE_URL.format(vin=vin)
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        return {"ok": False, "error": f"NHTSA request failed: {exc}", "vin": vin}

    results_list = data.get("Results") or []
    if not results_list:
        return {"ok": False, "error": "Empty NHTSA response", "vin": vin}

    r = results_list[0]
    error_code = _pick(r, "ErrorCode") or ""
    error_text = _pick(r, "ErrorText") or ""

    make = _pick(r, "Make")
    model = _pick(r, "Model")
    year_raw = _pick(r, "ModelYear")
    year = int(year_raw) if year_raw and year_raw.isdigit() else None

    engine_parts = [
        p
        for p in [
            _pick(r, "DisplacementL", "DisplacementCC"),
            _pick(r, "EngineCylinders"),
            _pick(r, "FuelTypePrimary"),
        ]
        if p
    ]
    engine = " / ".join(engine_parts) if engine_parts else None

    if not make and not model:
        return {
            "ok": False,
            "error": error_text or "Unable to decode VIN",
            "vin": vin,
            "error_code": error_code,
        }

    return {
        "ok": True,
        "vin": vin,
        "year": year,
        "make": make,
        "model": model,
        "engine": engine,
        "body_class": _pick(r, "BodyClass"),
        "drive_type": _pick(r, "DriveType"),
        "fuel_type": _pick(r, "FuelTypePrimary"),
        "plant_country": _pick(r, "PlantCountry"),
        "error_code": error_code,
        "error_text": error_text,
        "source": "nhtsa_vpic",
        "raw_keys_sample": {
            k: r.get(k)
            for k in (
                "Make",
                "Model",
                "ModelYear",
                "VehicleType",
                "BodyClass",
                "DriveType",
                "FuelTypePrimary",
                "DisplacementL",
                "EngineCylinders",
                "Manufacturer",
            )
        },
    }
