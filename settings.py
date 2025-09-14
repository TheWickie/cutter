"""
Settings for Cutter Voice Pilot (root layout).

Loads env vars (optionally via .env) and exposes normalized constants.
"""

import os
from dotenv import load_dotenv

# Load .env if present (harmless in production; Render uses dashboard vars)
load_dotenv()

# --- Core OpenAI config ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
if not OPENAI_API_KEY:
    # Keep running so /health works, but /session will fail fast upstream.
    # You can choose to raise here if you prefer a hard fail:
    # raise RuntimeError("OPENAI_API_KEY is required")
    pass

OPENAI_REALTIME_MODEL = os.getenv("OPENAI_REALTIME_MODEL", "gpt-4o-realtime-preview").strip()

# --- Server config ---
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8080"))

# --- CORS / Origin allow-list ---
# Comma-separated list of exact origins (no wildcards)
_raw_origins = os.getenv("ALLOWED_ORIGINS", "https://localhost,https://127.0.0.1")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

# --- Session TTL (no longer sent to OpenAI; kept for future/internal use) ---
EPHEMERAL_SESSION_TTL_SECONDS = int(os.getenv("EPHEMERAL_SESSION_TTL_SECONDS", "300"))

# --- Voice selection (used by /session) ---
# Default voice if none/invalid is requested.
VOICE_DEFAULT = os.getenv("OPENAI_REALTIME_VOICE", "alloy").strip() or "alloy"

# Comma-separated allow-list of voices you offer to users.
# You can change this from Render without code changes.
_voice_list = os.getenv("OPENAI_REALTIME_VOICES", "alloy,verse,aria").split(",")
VOICE_ALLOWED = {v.strip() for v in _voice_list if v.strip()}
if not VOICE_ALLOWED:
    VOICE_ALLOWED = {VOICE_DEFAULT}
