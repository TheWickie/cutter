import os
import httpx
from fastapi import APIRouter, HTTPException, Request

from core.redis_store import get_client, get_client_scheme
from core.rate_limit import rate_limit
from core.guardrails import get_excerpt

try:
    from loguru import logger
except Exception:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("cutter")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_REALTIME_MODEL = os.getenv("OPENAI_REALTIME_MODEL", "gpt-4o-realtime-preview")
OPENAI_REALTIME_VOICE = os.getenv("OPENAI_REALTIME_VOICE", "alloy")

router = APIRouter()

def _realtime_headers() -> dict:
    return {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "OpenAI-Beta": "realtime=v1",
        "Content-Type": "application/json",
    }

def _test_realtime_session() -> bool:
    """Try creating a session to verify access; discard response."""
    if not OPENAI_API_KEY:
        return False
    try:
        with httpx.Client(timeout=8.0) as client:
            r = client.post(
                "https://api.openai.com/v1/realtime/sessions",
                headers=_realtime_headers(),
                json={"model": OPENAI_REALTIME_MODEL, "voice": OPENAI_REALTIME_VOICE},
            )
        if r.status_code == 200:
            return True
        logger.warning("Realtime health probe failed: %s %s", r.status_code, r.text)
        return False
    except Exception as e:
        logger.exception("Realtime health probe error: %s", e)
        return False

@router.get("/v2/health")
def health(request: Request):
    rate_limit(request)
    # Redis check
    redis_ok = False
    try:
        c = get_client()
        key = "health:ping"
        c.incr(key)
        c.expire(key, 10)
        redis_ok = True
    except Exception as e:
        logger.exception("Redis health failed: %s", e)
        redis_ok = False

    # Realtime check
    openai_ok = _test_realtime_session()

    return {
        "service": "cutter",
        "redis_ok": redis_ok,
        "redis_scheme": get_client_scheme(),
        "openai_realtime_ok": openai_ok,
        "model": OPENAI_REALTIME_MODEL,
        "voice": OPENAI_REALTIME_VOICE,
        "rate_limit_per_minute": int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")),
    }

@router.get("/v2/guardrails")
def guardrails():
    return {"policy": get_excerpt()}

@router.post("/session")
def create_realtime_session(request: Request):
    rate_limit(request)

    # Dev fallback so local UI can load even without API key
    if not OPENAI_API_KEY:
        return {
            "client_secret": "dev-only",
            "model": OPENAI_REALTIME_MODEL,
        }

    try:
        resp = httpx.post(
            "https://api.openai.com/v1/realtime/sessions",
            headers=_realtime_headers(),
            json={"model": OPENAI_REALTIME_MODEL, "voice": OPENAI_REALTIME_VOICE},
            timeout=10.0,
        )
        if resp.status_code != 200:
            logger.error("Realtime session create failed: %s %s", resp.status_code, resp.text)
            raise HTTPException(
                status_code=502,
                detail={"error": {"code": "SESSION_CREATE_FAILED", "message": resp.text}},
            )
        data = resp.json()
        client_secret = data.get("client_secret")
        if isinstance(client_secret, dict):
            client_secret = client_secret.get("value")
        return {
            "client_secret": client_secret,
            "model": data.get("model", OPENAI_REALTIME_MODEL),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Realtime session create error: %s", exc)
        raise HTTPException(
            status_code=502,
            detail={"error": {"code": "SESSION_CREATE_FAILED", "message": str(exc)}},
        )
