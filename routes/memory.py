import datetime as dt
from fastapi import APIRouter, Request

from core.redis_store import get_json, set_json
from core.rate_limit import rate_limit
from schemas.memory import ProfilePatch, NoteBody

router = APIRouter(prefix="/v2/memory")


@router.get("/profile")
def get_profile(user_id: str, request: Request):
    rate_limit(request)
    memory = get_json(f"memory:{user_id}") or {}
    return {"user_id": user_id, "profile": memory.get("profile", {})}


@router.patch("/profile")
def patch_profile(body: ProfilePatch, request: Request):
    rate_limit(request)
    memory = get_json(f"memory:{body.user_id}") or {}
    profile = memory.get("profile", {})
    profile.update(body.patch)
    memory["profile"] = profile
    set_json(f"memory:{body.user_id}", memory)
    return {"user_id": body.user_id, "profile": profile}


@router.get("/notes")
def get_notes(user_id: str, request: Request):
    rate_limit(request)
    memory = get_json(f"memory:{user_id}") or {}
    return {"notes": memory.get("notes", [])}


@router.post("/notes")
def add_note(body: NoteBody, request: Request):
    rate_limit(request)
    memory = get_json(f"memory:{body.user_id}") or {}
    notes = memory.get("notes", [])
    notes.append({"ts": dt.datetime.utcnow().isoformat(), "note": body.note[:200]})
    memory["notes"] = notes[-20:]
    set_json(f"memory:{body.user_id}", memory)
    return {"status": "ok"}
