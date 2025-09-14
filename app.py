"""
Main application for the Cutter Voice Pilot backend.

This FastAPI app exposes two endpoints:

* ``GET /health`` — returns a simple JSON object to indicate the service
  is running.
* ``POST /session`` — validates the request origin, enforces per‑IP rate
  limiting, and then creates an OpenAI realtime session on behalf of the
  caller.  It returns the ``client_secret`` needed by the browser to
  establish a WebRTC connection.

The OpenAI API key is loaded from environment variables via the settings
module.  All sensitive information stays on the server; clients only
receive a short‑lived token.

See backend/README.md for further details.
"""

import time
import logging
from typing import Dict, List

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import settings

# Configure basic logging.  Avoid logging secrets such as tokens or API keys.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cutter_voice_pilot")


def create_app() -> FastAPI:
    """Factory to create a FastAPI app with CORS middleware and routes."""
    app = FastAPI(title="Cutter Voice Pilot Backend")

    # Configure CORS middleware.  Only the allowed origins may access the API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # In‑memory store for rate limiting by client IP.
    rate_limit_data: Dict[str, List[float]] = {}
    RATE_LIMIT = 10  # requests
    RATE_PERIOD = 60.0  # seconds

    # System instructions for the OpenAI realtime assistant.  These guardrails
    # ensure that the assistant behaves consistently with NA Traditions and
    # local safeguarding rules.  Do not include links or large excerpts of
    # literature to keep the TTS output concise.
    SYSTEM_PROMPT = (
        "You are **NA Interim Sponsor (Pilot)** for the UK North East Area. "
        "You are **not** a sponsor, clinician, therapist, or emergency service. "
        "You uphold NA spiritual principles (honesty, open‑mindedness, willingness, "
        "humility, compassion, unity, service) and NA Traditions (anonymity, "
        "non‑endorsement, autonomy). Always:\n"
        "• Start by asking for consent to proceed and remind the caller of privacy basics.\n"
        "• Encourage meetings, NA literature, and connection with members; you do not replace a sponsor.\n"
        "• If there is imminent risk (self‑harm, overdose, harm to others), say: “I’m worried about your safety.” "
        "Immediately offer **call 999** or **Samaritans 116 123**. In England, **NHS 111 (mental health option)** is "
        "available 24/7. Under‑18s: **Childline 0800 1111**. Offer to repeat numbers slowly.\n"
        "• Avoid medical/legal advice. If asked for health facts, share general public guidance briefly and encourage "
        "speaking to a medical professional or pharmacist.\n"
        "• Keep replies brief, supportive, and principle‑centred. Invite small next actions (e.g., “Would you like me to "
        "find a meeting tonight?”). Offer to send a short summary at the end.\n"
        "• Protect anonymity; never store or repeat identifying details unless the caller explicitly asks to save a "
        "note locally.\n"
        "• Use compassionate, non‑judgmental language. Validate feelings; suggest connection and practical next steps."
    )

    @app.get("/health")
    async def health() -> JSONResponse:
        """Health check endpoint.  Returns a simple JSON object."""
        return JSONResponse(content={"ok": True})

    @app.post("/session")
    async def create_session(request: Request) -> JSONResponse:
        """Create an OpenAI realtime session after validating origin and rate limits."""
        origin = request.headers.get("origin")
        # Validate the origin header against the allowed origins.
        if origin not in settings.ALLOWED_ORIGINS:
            logger.warning("Rejected session request from disallowed origin: %s", origin)
            raise HTTPException(status_code=403, detail="Origin not allowed")

        # Enforce simple per‑IP rate limiting.
        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window_start = now - RATE_PERIOD
        timestamps = rate_limit_data.get(client_ip, [])
        # Retain only timestamps within the current window.
        timestamps = [t for t in timestamps if t > window_start]
        if len(timestamps) >= RATE_LIMIT:
            logger.info("Rate limit exceeded for %s", client_ip)
            raise HTTPException(status_code=429, detail="Too many requests, please slow down.")
        # Record this request.
        timestamps.append(now)
        rate_limit_data[client_ip] = timestamps

        # Prepare the payload for OpenAI realtime session creation.
        payload = {
            "model": settings.OPENAI_REALTIME_MODEL,
            "voice": "alloy",
            "modalities": ["audio", "text"],
            "instructions": SYSTEM_PROMPT,
            "expires_in": settings.EPHEMERAL_SESSION_TTL_SECONDS,
        }

        # Use an async HTTP client for the API call.
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://api.openai.com/v1/realtime/sessions",
                    json=payload,
                    headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                    timeout=15.0,
                )
            except httpx.HTTPError as exc:
                logger.error("Error connecting to OpenAI API: %s", exc)
                raise HTTPException(status_code=503, detail="Upstream service unavailable") from exc

        if response.status_code != 200:
            # If the OpenAI API returns an error, propagate a generic message.
            logger.error(
                "OpenAI realtime session creation failed: %s - %s",
                response.status_code,
                response.text,
            )
            raise HTTPException(
                status_code=response.status_code,
                detail="Failed to create realtime session",
            )

        # Parse the response JSON.  It should contain client_secret, model and expires_at.
        data = response.json()
        client_secret = data.get("client_secret")
        model = data.get("model")
        expires_at = data.get("expires_at")

        return JSONResponse(
            content={
                "client_secret": client_secret,
                "model": model,
                "expires_at": expires_at,
            }
        )

    return app


# Instantiate the application to be used by Uvicorn.
app = create_app()