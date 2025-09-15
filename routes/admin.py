import os
import uuid
import datetime as dt
from fastapi import APIRouter, HTTPException, Request

from core.redis_store import get_client
from core.rate_limit import rate_limit
from core.auth_utils import normalize_name, hash_passphrase, verify_passphrase, normalize_pass_for_debug
from schemas.admin import AdminUserUpsert, AdminVerifyPass

router = APIRouter(prefix="/v2/admin")

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")


def _require_admin(request: Request) -> None:
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail={"error": {"code": "ADMIN_DISABLED", "message": "ADMIN_TOKEN not set"}})
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or auth.split(" ", 1)[1] != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail={"error": {"code": "UNAUTHORISED", "message": "Bad admin token"}})


@router.get("/health")
def health(request: Request):
    """Admin health: verifies admin token and Redis connectivity."""
    rate_limit(request)
    _require_admin(request)
    ok = False
    try:
        c = get_client()
        c.ping()
        ok = True
    except Exception:
        ok = False
    return {"admin": "ok", "redis_ok": ok}


@router.post("/user")
def upsert_user(body: AdminUserUpsert, request: Request):
    rate_limit(request)
    _require_admin(request)

    r = get_client()
    now = dt.datetime.utcnow().isoformat()

    user_id = None
    status = "created"

    # Try to find an existing user by id_code or display_name mapping
    if body.id_code:
        user_id = r.get(f"idcode_to_user:{body.id_code.strip().upper()}")
    if not user_id and body.display_name:
        user_id = r.get(f"name_to_user:{normalize_name(body.display_name)}")

    if not user_id:
        user_id = uuid.uuid4().hex
    else:
        status = "updated"

    # Reverse mappings
    if body.id_code:
        r.set(f"idcode_to_user:{body.id_code.strip().upper()}", user_id)
    if body.number:
        r.set(f"number_to_user:{body.number.strip()}", user_id)
    if body.display_name:
        r.set(f"name_to_user:{normalize_name(body.display_name)}", user_id)

    # User hash
    mapping = {
        "name": body.name.strip(),
        "number": (body.number or "").strip(),
        "id_code": (body.id_code or "").strip().upper(),
        "authed": "1",
        "last_seen": now,
    }
    # Only set created_at if new
    if status == "created":
        mapping["created_at"] = now
    r.hset(f"user:{user_id}", mapping=mapping)

    if body.passphrase:
        # Strip accidental surrounding quotes and normalise inside hash_passphrase
        pp = body.passphrase.strip().strip('"').strip("'")
        salt_hex, hash_hex = hash_passphrase(pp)
        r.hset(f"user:{user_id}", mapping={"pass_salt": salt_hex, "pass_hash": hash_hex})
    user_after = r.hgetall(f"user:{user_id}")
    has_pp = bool(user_after.get("pass_salt") and user_after.get("pass_hash"))
    return {"user_id": user_id, "status": status, "has_passphrase": has_pp}


@router.post("/verify-pass")
def verify_pass(body: AdminVerifyPass, request: Request):
    rate_limit(request)
    _require_admin(request)
    r = get_client()
    dn = normalize_name(body.display_name)
    uid = r.get(f"name_to_user:{dn}")
    if not uid:
        return {"ok": False, "reason": "NO_SUCH_USER"}
    user = r.hgetall(f"user:{uid}")
    salt = user.get("pass_salt", "")
    phash = user.get("pass_hash", "")
    if not salt or not phash:
        return {"ok": False, "reason": "NO_PASSPHRASE", "user_id": uid}
    ok = verify_passphrase(salt, phash, body.passphrase)
    return {"ok": bool(ok), "user_id": uid, **({"reason": "MISMATCH"} if not ok else {})}


@router.get("/user-by-display")
def user_by_display(display_name: str, request: Request):
    rate_limit(request)
    _require_admin(request)
    r = get_client()
    dn = normalize_name(display_name)
    uid = r.get(f"name_to_user:{dn}")
    if not uid:
        return {"found": False}
    user = r.hgetall(f"user:{uid}")
    has_pp = bool(user.get("pass_salt") and user.get("pass_hash"))
    safe = {
        "user_id": uid,
        "name": user.get("name"),
        "number": user.get("number"),
        "id_code": user.get("id_code"),
        "has_passphrase": has_pp,
    }
    return {"found": True, **safe}


@router.post("/debug-pass")
def debug_pass(body: AdminVerifyPass, request: Request):
    """Admin-only debug endpoint to inspect normalization and verify outcome.

    Returns only non-sensitive diagnostics. It echoes the normalized attempt
    because the admin typed it, but never returns stored salts or hashes.
    """
    rate_limit(request)
    _require_admin(request)
    r = get_client()
    dn = normalize_name(body.display_name)
    uid = r.get(f"name_to_user:{dn}")
    found = bool(uid)
    result: dict = {
        "found": found,
        "display_name_normalized": dn,
    }
    if not found:
        return result
    user = r.hgetall(f"user:{uid}")
    salt = user.get("pass_salt", "")
    phash = user.get("pass_hash", "")
    has_pp = bool(salt and phash)
    norm = normalize_pass_for_debug(body.passphrase)
    verified = bool(has_pp and verify_passphrase(salt, phash, body.passphrase))
    contains_zero_width = any(ch in body.passphrase for ch in ["\u200B", "\u200C", "\u200D", "\uFEFF"])
    result.update(
        {
            "user_id": uid,
            "has_passphrase": has_pp,
            "attempt_input_len": len(body.passphrase or ""),
            "attempt_norm_len": len(norm),
            "attempt_norm": norm,
            "verified": verified,
            "contains_zero_width_input": contains_zero_width,
        }
    )
    return result
