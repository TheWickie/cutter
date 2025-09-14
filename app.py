# app.py
"""
Cutter Voice Pilot – FastAPI backend (root layout)

Endpoints:
  GET  /health   -> { ok: True }
  POST /session  -> { client_secret, model, expires_at }

Notes:
- This file lives at the repo root next to settings.py.
- Uses module import (import settings), not a relative import.
- Defines `app` (lowercase) so `uvicorn app:app` works on Render.
"""

import ipaddress
import os
import time
from collections import deque
from typing import Deque, Dict

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import settings  # <-- important: root-level import, no leading dot

app = FastAPI(title="Cutter Voice Pilot", version="0.1.0")

# CORS: exact origins only
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Very light per-IP rate limit (10 req/min)
_RATE_WINDOW = 60.0
_RATE_MAX = 10
_hits: Dict[str, Deque[float]] = {}


def _client_ip(req: Request) -> str:
    xff = req.headers.get("x-forwarded-for", "")
    ip = xff.split(",")[0].strip() if xff else (req.client.host if req.client else "0.0.0.0")
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        ip = "0.0.0.0"
    return ip


def _rate_limit(ip: str) -> None:
    now = time.time()
    dq = _hits.setdefault(ip, deque())
    while dq and (now - dq[0]) > _RATE_WINDOW:
        dq.popleft()
    if len(dq) >= _RATE_MAX:
        raise HTTPException(status_code=429, detail="Too many requests, slow down.")
    dq.append(now)


def _check_origin(req: Request) -> None:
    origin = req.headers.get("origin")
    if not origin:
        raise HTTPException(status_code=400, detail="Missing Origin header.")
    if origin not in settings.ALLOWED_ORIGINS:
        raise HTTPException(status_code=403, detail=f"Origin not allowed: {origin}")


NA_GUARDRAILS = (
    "You are **NA Interim Sponsor (Pilot)** for the UK North East Area. "
    "You are **not** a sponsor, clinician, therapist, or emergency service. "
    "You uphold NA spiritual principles (honesty, open-mindedness, willingness, humility, compassion, unity, service) "
    "and NA Traditions (anonymity, non-endorsement, autonomy). Always:\n"
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


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/session")
async def create_session(request: Request):
    _check_origin(request)
    _rate_limit(_client_ip(request))

    url = "https://api.openai.com/v1/realtime/sessions"
    payload = {
        "model": settings.OPENAI_REALTIME_MODEL,
        "modalities": ["audio", "text"],
        "voice": "alloy",
        "instructions": NA_GUARDRAILS,
        "expires_in": settings.EPHEMERAL_SESSION_TTL_SECONDS,
        # "input_audio_format": "pcm16",  # optional
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
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        raise HTTPException(status_code=resp.status_code, detail=detail)

    return JSONResponse(resp.json())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "8080")),
        reload=True,
    )
