import os
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from core.redis_store import get_json, set_json
from core.rate_limit import rate_limit

router = APIRouter(prefix="/v2/chat/voice")

SESSION_TTL = int(os.getenv("SESSION_TTL_SECONDS", "3600"))
VOICE_ALLOWED = {v.strip() for v in os.getenv("VOICE_ALLOWED", "alloy,verse,amber,copper").split(",") if v.strip()}


class VoiceStart(BaseModel):
    session_id: str
    voice: str


@router.post("/start")
def start(body: VoiceStart, request: Request):
    rate_limit(request)
    if body.voice not in VOICE_ALLOWED:
        raise HTTPException(status_code=400, detail={"error": {"code": "BAD_VOICE", "message": "Voice not allowed"}})
    session = get_json(f"session:{body.session_id}")
    if not session:
        raise HTTPException(status_code=401, detail={"error": {"code": "BAD_SESSION", "message": "Session not found"}})
    session["mode"] = "voice"
    set_json(f"session:{body.session_id}", session, ttl=SESSION_TTL)
    return {"token": f"{body.session_id}-voice", "voice": body.voice}


class VoiceStop(BaseModel):
    session_id: str


@router.post("/stop")
def stop(body: VoiceStop, request: Request):
    rate_limit(request)
    session = get_json(f"session:{body.session_id}")
    if session:
        session["mode"] = "text"
        set_json(f"session:{body.session_id}", session, ttl=SESSION_TTL)
    return {"status": "stopped"}
