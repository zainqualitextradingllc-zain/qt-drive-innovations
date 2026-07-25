from typing import Any, Literal

from pydantic import BaseModel, Field

from .diagnosis import DiagnosisPayload


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class VehicleContext(BaseModel):
    vin: str | None = None
    year: int | None = None
    make: str | None = None
    model: str | None = None
    engine: str | None = None
    source: Literal["nhtsa_vpic", "user_reported", "unknown"] = "unknown"
    raw: dict[str, Any] | None = None


class ChatRequest(BaseModel):
    session_id: str | None = None
    language: Literal["en", "ja"] = "en"
    message: str = Field(min_length=1, max_length=4000)
    messages: list[ChatMessage] = Field(default_factory=list)
    vehicle: VehicleContext | None = None


class ChatResponse(BaseModel):
    session_id: str
    language: Literal["en", "ja"]
    reply: str
    mode: Literal["question", "diagnosis", "info", "error"]
    vehicle: VehicleContext | None = None
    diagnosis: DiagnosisPayload | None = None
    questions_asked_count: int = 0
    intent: str = "car_diagnostics"
    rag_hits: list[dict[str, Any]] = Field(default_factory=list)
    # Phase 4a.0 integrity (optional; omit/null if attestation failed)
    content_hash: str | None = None
    diagnosis_id: str | None = None
