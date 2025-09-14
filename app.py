# app.py
"""
Cutter Voice Pilot – FastAPI backend

Endpoints:
  GET  /health   -> { ok: True }
  POST /session  -> returns { client_secret, model, expires_at } for OpenAI Realtime

Notes:
- Expects settings.py in the same directory (module import, not package import).
- Enforces Origin allow-list and simple per-IP rate limiting.
- Never exposes OPENAI_API_KEY to the browser.
"""

import os
import time
import ipaddress
from typing import Dict, Deque
from collections import deque

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# IMPORTANT: now that files are at repo ROOT, use module import (no leading dot)
import settings  # <-- this is the change vs the earlier relative import


APP = FastAPI(title="Cutter Voice Pilot", version="0.1.0")

# CORS: allow only configured origins
APP.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

# In-memory token bucket per IP (very light; restarts clear it)
RATE_LIMIT_WINDOW_SEC = 60
RATE_LIMIT_MAX_HITS = 10
_recent_hits: Dict[str, Deque[float]] = {}


def _client_ip(req: Request) -> str:
    # Respect common proxy headers if present (Render puts X-Forwarded-For)
    xff = req.headers.get("x-forwarded-for", "")
    ip = xff.split(",")[0].strip() if xff else req.client.host
    # Normalise: ensure it parses as IP (fallback to req.client.host)
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        ip = req.client.host
    return ip


def _rate_limit(ip: str) -> None:
    now = time.time()
    dq = _recent_hits.setdefault(ip, deque())
    # drop old entries
    while dq and now - dq[0] > RATE_LIMIT_WINDOW_SEC:
        dq.popleft()
    if len(dq) >= RATE_LIMIT_MAX_HITS:
        raise HTTPException(status_code=429, detail="Too many requests, please slow down.")
    dq.append(now)


def _check_origin(req: Request) -> None:
    origin = req.headers.get("origin")
    if not origin:
        # Block calls without Origin to avoid cross-site misuse
        raise HTTPException(status_code=400, detail="Missing Origin header.")
    # Exact match only (no wildcard)
    if origin not in settings.ALLOWED_ORIGINS:
        raise HTTPException(status_code=403, detail=f"Origin not allowed: {origin}")


NA_GUARDRAILS = (
    "You are **NA Interim Sponsor (Pilot)** for the UK North East Area. "
    "You are **not** a sponsor, clinician, therapist, or emergency service. "
    "You uphold NA spiritual principles (honesty, open-mindedness, willingness, humility, "
    "compassion, unity, service) and NA Traditions (anonymity, non-endorsement, autonomy). "
    "Always:\n"
    "• Start by asking for consent to proceed and remind the caller of privacy basics.\n"
    "• Encourage meetings, NA literature, and connection with members; you do not replace a sponsor.\n"
    "• If there is imminent risk (self-harm, overdose, harm to others), say: “I’m worried about your safety.” "
    "Immediately offer call 999 or Samaritans 116 123. In England, NHS 111 (mental health option) is available 24/7. "
    "Under-18s: Childline 0800 1111. Offer to repeat numbers slowly.\n"
    "• Avoid medical/legal advice. If asked for health facts, share general public guidance briefly and encourage speaking "
    "to a medical professional or pharmacist.\n"
    "• Keep replies brief, supportive, and principle-centred. Invite small next actions (e.g., "
    "“Would you like me to find a meeting tonight?”). Offer to send a short summary at the end.\n"
    "• Protect anonymity; never store or repeat identifying details unless the caller explicitly asks to save a note locally.\n"
    "• Use compassionate, non-judgmental language. Validate feelings; suggest connection and practical next steps."
)


@APP.get("/health")
async def health():
    return {"ok": True}


@APP.post("/session")
async def create_session(request: Request):
    _check_origin(request)
    _rate_limit(_client_ip(request))

    # Create an ephemeral OpenAI Realtime session
    url = "https://api.openai.com/v1/realtime/sessions"
    payload = {
        "model": settings.OPENAI_REALTIME_MODEL,
        "modalities": ["audio", "text"],
        "voice": "alloy",
        "instructions": NA_GUARDRAILS,
        "expires_in": settings.EPHEMERAL_SESSION_TTL_SECONDS,
        # Optional: you can include `input_audio_format` if you want to force PCM16
        # "input_audio_format": "pcm16",
    }

    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Upstream error: {e!s}")

    if resp.status_code >= 400:
        # Redact secrets; pass through upstream message for debugging
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        raise HTTPException(status_code=resp.status_code, detail=detail)

    data = resp.json()
    # Expected keys: client_secret, model, expires_at
    # Return them as-is, but never log them.
    return JSONResponse(data)


# If you prefer to run with `python app.py` locally for quick checks:
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:APP", host=os.getenv("APP_HOST", "0.0.0.0"), port=int(os.getenv("APP_PORT", "8080")), reload=True)
