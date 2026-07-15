from fastapi import APIRouter, HTTPException

from app.models.chat import ChatRequest, ChatResponse
from app.services.orchestrator import process_chat
from app.tools.vin import decode_vin_nhtsa

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message is required")
    return await process_chat(req)


@router.get("/vin/{vin}")
async def vin_decode(vin: str):
    result = await decode_vin_nhtsa(vin)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "Decode failed")
    return result
