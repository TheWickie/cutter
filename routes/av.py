import os
import re
import json
import hashlib
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, Request

from core.redis_store import get_client
from core.rate_limit import rate_limit
from routes.admin import _require_admin  # reuse token check

try:
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

router = APIRouter(prefix="/v2/av")


def _slug(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", (s or "").strip())
    return s.strip("-").lower() or "audio"


@router.post("/captions")
def captions(body: Dict[str, Any], request: Request):
    """Generate timed caption overlays for an audio track.

    Request body:
      { title: str, duration_seconds: number, keywords?: [str], count?: int }

    Requires ADMIN_TOKEN. Caches results in Redis by title+duration.
    """
    rate_limit(request)
    _require_admin(request)
    title = str(body.get("title") or "Untitled")
    duration = float(body.get("duration_seconds") or 0)
    if duration <= 0:
        raise HTTPException(status_code=400, detail="duration_seconds must be > 0")
    count = int(body.get("count") or 12)
    count = max(6, min(count, 24))
    keywords = body.get("keywords") or []
    if not isinstance(keywords, list):
        keywords = []

    # Cache key
    key_src = json.dumps({"t": title, "d": round(duration), "k": keywords, "c": count})
    key_hash = hashlib.sha256(key_src.encode("utf-8")).hexdigest()[:16]
    rkey = f"audio:captions:{_slug(title)}:{round(duration)}:{key_hash}"
    r = get_client()
    cached = r.get(rkey)
    if cached:
        try:
            return {"overlays": json.loads(cached), "cached": True}
        except Exception:
            pass

    # Build prompt
    kw = ", ".join([str(k) for k in keywords if isinstance(k, (str, int, float))])
    prompt = (
        "You are helping produce short, meaningful on-screen text overlays for an audio track.\n"
        "Given a track title, duration and optional keywords, output a JSON array of objects: \n"
        "[{\"t\": seconds_from_start_float, \"text\": short_overlay_text}]\n"
        "Rules: \n"
        "- Create exactly "
        + str(count)
        + " overlays across the track, evenly covering the duration.\n"
        "- t must be strictly increasing, between 1.0 and duration-1.0.\n"
        "- text should be 2-8 words, positive, relevant, non-repetitive.\n"
        "- Do not add any commentary, only pure JSON array.\n"
        f"Track: title='{title}', duration={round(duration)}s, keywords=[{kw}]\n"
        "Return only the JSON array."
    )

    overlays: List[Dict[str, Any]] = []
    # Try OpenAI; fallback to simple slices
    client = OpenAI(api_key=OPENAI_API_KEY) if (OpenAI and OPENAI_API_KEY) else None
    if client:
        try:
            resp = client.chat.completions.create(
                model=OPENAI_CHAT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            content = (
                getattr(resp.choices[0].message, "content", None)
                if hasattr(resp.choices[0], "message")
                else None
            )
            if not content and isinstance(resp.choices[0], dict):
                content = resp.choices[0].get("message", {}).get("content")
            if not content:
                content = "[]"
            parsed = json.loads(content)
            if isinstance(parsed, list):
                # Validate items
                for it in parsed:
                    try:
                        t = float(it.get("t"))
                        txt = str(it.get("text") or "").strip()
                        if 0.5 <= t <= (duration - 0.5) and txt:
                            overlays.append({"t": float(t), "text": txt[:80]})
                    except Exception:
                        continue
        except Exception:
            overlays = []

    if not overlays:
        # Fallback evenly spaced captions
        step = duration / (count + 1)
        phrases = [
            "Breathe and listen",
            "Stay present",
            "Let thoughts pass",
            "Feel the rhythm",
            "Embrace the moment",
            "You are enough",
            "Gratitude grows",
            "One step at a time",
            "Choose kindness",
            "Progress, not perfection",
            "Calm within",
            "Keep going",
        ]
        for i in range(count):
            overlays.append({"t": round((i + 1) * step, 2), "text": phrases[i % len(phrases)]})

    # Cache
    try:
        r.set(rkey, json.dumps(overlays))
    except Exception:
        pass
    return {"overlays": overlays, "cached": False}

