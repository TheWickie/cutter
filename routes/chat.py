import os
import datetime as dt
from fastapi import APIRouter, HTTPException, Request

try:
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None

from core.redis_store import get_json, set_json, hgetall, touch_last_seen
from core.guardrails import build_system_prompt
from core.rate_limit import rate_limit
from schemas.chat import ChatSend

router = APIRouter(prefix="/v2/chat")

SESSION_TTL = int(os.getenv("SESSION_TTL_SECONDS", "3600"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

client = OpenAI(api_key=OPENAI_API_KEY) if (OpenAI and OPENAI_API_KEY) else None


@router.post("/send")
async def send(body: ChatSend, request: Request):
    rate_limit(request)
    session = get_json(f"session:{body.session_id}")
    if not session:
        raise HTTPException(status_code=401, detail={"error": {"code": "BAD_SESSION", "message": "Session not found"}})
    user_id = session["user_id"]
    profile = hgetall(f"user:{user_id}")
    memory = get_json(f"memory:{user_id}") or {}
    history = session.get("state", {}).get("history", [])

    system_prompt = build_system_prompt(profile, memory)

    reply_text = "This is a test reply."  # fallback
    if client:
        messages = [{"role": "system", "content": system_prompt}] + history + [
            {"role": "user", "content": body.message}
        ]
        try:
            resp = client.chat.completions.create(model=OPENAI_CHAT_MODEL, messages=messages)
            reply_text = resp.choices[0].message["content"]
        except Exception:
            reply_text = "Sorry, I had trouble responding."  # graceful fallback

    history.append({"role": "user", "content": body.message})
    history.append({"role": "assistant", "content": reply_text})
    session["state"] = {"history": history[-50:]}
    set_json(f"session:{body.session_id}", session, ttl=SESSION_TTL)

    memory["last_topics"] = body.message[:50]
    memory["last_contact"] = dt.datetime.utcnow().isoformat()
    set_json(f"memory:{user_id}", memory)
    touch_last_seen(user_id)

    return {"reply": reply_text, "memory_delta": {"last_topics": memory.get("last_topics")}}


@router.get("/history")
def history(session_id: str, request: Request):
    rate_limit(request)
    session = get_json(f"session:{session_id}")
    if not session:
        raise HTTPException(status_code=401, detail={"error": {"code": "BAD_SESSION", "message": "Session not found"}})
    return {"history": session.get("state", {}).get("history", [])[-25:]}
