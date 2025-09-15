import os
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from core.redis_store import get_client
from core.guardrails import get_excerpt

router = APIRouter()


@router.get("/v2/health")
def health():
    ok = True
    try:
        get_client().ping()
    except Exception:
        ok = False
    return {"status": "ok", "redis": "ok" if ok else "error"}


@router.get("/v2/config")
def config():
    voices = [v.strip() for v in os.getenv("VOICE_ALLOWED", "").split(",") if v.strip()]
    return {"voices": voices}


@router.get("/v2/guardrails")
def guardrails():
    return {"policy": get_excerpt()}


@router.post("/session")
def deprecated_session():
    return JSONResponse(
        {"error": {"code": "DEPRECATED", "message": "Use /v2/auth/* and /v2/chat/*"}},
        status_code=410,
    )
