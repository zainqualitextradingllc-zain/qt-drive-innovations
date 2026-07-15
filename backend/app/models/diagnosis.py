from typing import Literal

from pydantic import BaseModel, Field


class DiagnosisCause(BaseModel):
    cause: str
    confidence: float = Field(ge=0, le=100)
    rationale: str | None = None


class VehicleContextModel(BaseModel):
    vin: str | None = None
    year: int | None = None
    make: str | None = None
    model: str | None = None
    engine: str | None = None
    source: Literal["nhtsa_vpic", "user_reported", "unknown"] = "unknown"


class DiagnosisPayload(BaseModel):
    language: Literal["en", "ja"]
    vehicle_context: VehicleContextModel | None = None
    diagnosis: list[DiagnosisCause] = Field(min_length=1, max_length=3)
    severity: str
    severity_code: Literal["safe_to_drive", "caution", "stop_immediately"]
    estimated_cost: str
    currency: Literal["USD", "JPY"]
    cost_min: float | None = None
    cost_max: float | None = None
    next_action: str
    related_obd_codes: list[str] = Field(default_factory=list)
    questions_asked_count: int = 0
    confidence_overall: float | None = None
    assumptions: list[str] = Field(default_factory=list)
    safety_flags: list[str] = Field(default_factory=list)
    disclaimer: str
