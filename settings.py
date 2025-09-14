"""
Settings module for Cutter Voice Pilot backend.

This module loads configuration from environment variables (optionally via a
``.env`` file using python‑dotenv) and exposes them as constants.  It also
normalises certain values, such as allowed origins and TTLs.
"""

import os
from dotenv import load_dotenv

# Load environment variables from a .env file if present.
load_dotenv()

# OpenAI API key used for server‑side calls.  Never expose this to clients.
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

# Name of the OpenAI realtime model to use.  Defaults to the current stable
# realtime model if not specified.
OPENAI_REALTIME_MODEL: str = os.getenv(
    "OPENAI_REALTIME_MODEL", "gpt-4o-realtime-preview"
)

# Comma‑separated list of allowed origins for CORS.  Split and strip empty
# entries to form a list.  For example: "https://localhost,https://127.0.0.1".
ALLOWED_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

# TTL for realtime session tokens in seconds.  Defaults to 5 minutes.
try:
    EPHEMERAL_SESSION_TTL_SECONDS: int = int(
        os.getenv("EPHEMERAL_SESSION_TTL_SECONDS", "300")
    )
except ValueError:
    EPHEMERAL_SESSION_TTL_SECONDS = 300

# Host and port for the FastAPI application.
APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
try:
    APP_PORT: int = int(os.getenv("APP_PORT", "8080"))
except ValueError:
    APP_PORT = 8080

# ElevenLabs configuration stub – left here for future expansion.  Do not
# implement TTS switching now; see backend/README.md for details.
ELEVENLABS_API_KEY: str | None = os.getenv("ELEVENLABS_API_KEY")