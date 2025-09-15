import os
import uuid
import datetime as dt
from fastapi import APIRouter, HTTPException, Request

from core.redis_store import get_client, hgetall, hset, set_json
from core.rate_limit import rate_limit
from schemas.auth import CallRequest, VerifyNameRequest, ModeRequest

router = APIRouter(prefix="/v2")

SESSION_TTL = int(os.getenv("SESSION_TTL_SECONDS", "3600"))


@router.post("/auth/call")
def call(body: CallRequest, request: Request):
    rate_limit(request)
    r = get_client()
    user_id = r.get(f"number_to_user:{body.number}")
    if user_id:
        return {"user_id": user_id, "need_name_verification": True}
    return {"need_name_registration": True}


@router.post("/auth/verify-name")
def verify(body: VerifyNameRequest, request: Request):
    rate_limit(request)
    r = get_client()
    user_id = r.get(f"number_to_user:{body.number}")
    now = dt.datetime.utcnow().isoformat()
    if user_id:
        profile = hgetall(f"user:{user_id}")
        if profile and profile.get("name") and profile.get("name") != body.name:
            raise HTTPException(status_code=401, detail={"error": {"code": "BAD_NAME", "message": "Name mismatch"}})
    else:
        user_id = uuid.uuid4().hex
        r.set(f"number_to_user:{body.number}", user_id)
    hset(
        f"user:{user_id}",
        {
            "name": body.name,
            "number": body.number,
            "authed": "1",
            "created_at": now,
            "last_seen": now,
        },
    )
    session_id = uuid.uuid4().hex
    session = {
        "user_id": user_id,
        "mode": "text",
        "created_at": now,
        "expires_at": (dt.datetime.utcnow() + dt.timedelta(seconds=SESSION_TTL)).isoformat(),
        "state": {"history": []},
    }
    set_json(f"session:{session_id}", session, ttl=SESSION_TTL)
    return {"user_id": user_id, "session_id": session_id, "mode": "text"}


@router.post("/session/mode")
def session_mode(body: ModeRequest, request: Request):
    rate_limit(request)
    session_raw = get_client().get(f"session:{body.session_id}")
    if not session_raw:
        raise HTTPException(status_code=401, detail={"error": {"code": "BAD_SESSION", "message": "Session not found"}})
    import json
    session_obj = json.loads(session_raw)
    session_obj["mode"] = body.mode
    set_json(f"session:{body.session_id}", session_obj, ttl=SESSION_TTL)
    return {"session_id": body.session_id, "mode": body.mode}
