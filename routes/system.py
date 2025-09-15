import os
import httpx
from fastapi import APIRouter, HTTPException, Request

from core.redis_store import get_client
from core.guardrails import get_excerpt
from core.rate_limit import rate_limit

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_REALTIME_MODEL = os.getenv("OPENAI_REALTIME_MODEL", "gpt-4o-realtime-preview")
OPENAI_REALTIME_VOICE = os.getenv("OPENAI_REALTIME_VOICE", "alloy")

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
def create_session(request: Request):
    rate_limit(request)
    if not OPENAI_API_KEY:
        return {"client_secret": "test_secret", "model": OPENAI_REALTIME_MODEL}
    try:
        resp = httpx.post(
            "https://api.openai.com/v1/realtime/sessions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"model": OPENAI_REALTIME_MODEL, "voice": OPENAI_REALTIME_VOICE},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "client_secret": data.get("client_secret"),
            "model": data.get("model", OPENAI_REALTIME_MODEL),
        }
    except Exception as exc:  # pragma: no cover - network errors
        raise HTTPException(
            status_code=502,
            detail={"error": {"code": "SESSION_CREATE_FAILED", "message": str(exc)}},
        )
