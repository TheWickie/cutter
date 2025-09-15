import os
import uuid
import datetime as dt
from fastapi import APIRouter, HTTPException, Request

from core.redis_store import get_client
from core.rate_limit import rate_limit
from core.auth_utils import normalize_name, hash_passphrase
from schemas.admin import AdminUserUpsert

router = APIRouter(prefix="/v2/admin")

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")


def _require_admin(request: Request) -> None:
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail={"error": {"code": "ADMIN_DISABLED", "message": "ADMIN_TOKEN not set"}})
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or auth.split(" ", 1)[1] != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail={"error": {"code": "UNAUTHORISED", "message": "Bad admin token"}})


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
        salt_hex, hash_hex = hash_passphrase(body.passphrase)
        r.hset(f"user:{user_id}", mapping={"pass_salt": salt_hex, "pass_hash": hash_hex})

    return {"user_id": user_id, "status": status}

