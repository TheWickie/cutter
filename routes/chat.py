import os
import re
import datetime as dt
from fastapi import APIRouter, HTTPException, Request

try:
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None

from core.redis_store import get_json, set_json, hgetall, touch_last_seen, get_client
from core.guardrails import build_system_prompt
from core.lit_index import search as lit_search, build_context as lit_context
from core.rate_limit import rate_limit
from schemas.chat import ChatSend
from core.auth_utils import extract_claimed_name, verify_passphrase

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
    r = get_client()
    state = session.get("state", {})
    history = state.get("history", [])

    # Lightweight identity handshake: detect name claim and ask for passphrase.
    text = (body.message or "").strip()
    ident = state.get("identity", {})
    if ident.get("stage") == "await_pass":
        cand_uid = ident.get("candidate_user_id")
        user_hash = hgetall(f"user:{cand_uid}")
        salt = user_hash.get("pass_salt", "")
        phash = user_hash.get("pass_hash", "")
        ok = bool(salt and phash and verify_passphrase(salt, phash, text))
        if ok:
            session["user_id"] = cand_uid
            state.pop("identity", None)
            session["state"] = {**state, "history": history[-50:]}
            set_json(f"session:{body.session_id}", session, ttl=SESSION_TTL)
            profile = hgetall(f"user:{cand_uid}")
            name = profile.get("name", "there")
            return {"reply": f"Thanks, {name}. I’ve opened your notes. How can I help today?", "memory_delta": {}}
        else:
            tries = int(ident.get("tries", 0)) + 1
            if tries >= 3:
                state.pop("identity", None)
                session["state"] = {**state, "history": history[-50:]}
                set_json(f"session:{body.session_id}", session, ttl=SESSION_TTL)
                return {"reply": "That didn’t match. We can continue as guest for now.", "memory_delta": {}}
            else:
                state.setdefault("identity", {})
                state["identity"]["tries"] = tries
                session["state"] = {**state, "history": history[-50:]}
                set_json(f"session:{body.session_id}", session, ttl=SESSION_TTL)
                return {"reply": "That didn’t match. Try again, please.", "memory_delta": {}}

    claimed = extract_claimed_name(text)
    if claimed:
        cand_uid = r.get(f"name_to_user:{claimed}")
        if cand_uid:
            state["identity"] = {"stage": "await_pass", "candidate_user_id": cand_uid, "tries": 0}
            session["state"] = {**state, "history": history[-50:]}
            set_json(f"session:{body.session_id}", session, ttl=SESSION_TTL)
            return {"reply": "What’s your passphrase please?", "memory_delta": {}}

    profile = hgetall(f"user:{user_id}")
    memory = get_json(f"memory:{user_id}") or {}

    # Build system prompt and optional NA literature context for stepwork queries
    system_prompt = build_system_prompt(profile, memory)
    lit_snippets = []
    # Simple heuristic: if user mentions step or sponsor/literature terms, retrieve context
    lower_msg = (body.message or "").lower()
    if any(t in lower_msg for t in ["step ", "step", "sponsor", "literature", "na text", "basic text", "just for today", "swg", "step one", "step 1", "step two", "step 2", "powerless", "higher power", "inventory"]):
        try:
            lit_snippets = lit_search(body.message, k=3)
        except Exception:
            lit_snippets = []
    if lit_snippets:
        system_prompt = system_prompt + "\n\nContext:\n" + lit_context(lit_snippets)

    reply_text = "This is a test reply."  # fallback
    if client:
        messages = [{"role": "system", "content": system_prompt}] + history + [
            {"role": "user", "content": body.message}
        ]
        try:
            resp = client.chat.completions.create(model=OPENAI_CHAT_MODEL, messages=messages)
            choice = resp.choices[0]
            # Support both dict-like and object-like message
            msg = getattr(choice, "message", None)
            content = None
            if msg is not None:
                content = getattr(msg, "content", None)
                if content is None and isinstance(msg, dict):
                    content = msg.get("content")
            if not content:
                content = ""
            reply_text = str(content).strip() or "I’m here. How can I help?"
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
