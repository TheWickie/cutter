import os
from fastapi import HTTPException, Request
from .redis_store import get_client

RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))


def get_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


def rate_limit(request: Request) -> None:
    ip = get_ip(request)
    key = f"rate:{ip}"
    client = get_client()
    count = client.incr(key)
    if count == 1:
        client.expire(key, 60)
    if count > RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=429, detail={"error": {"code": "RATE_LIMIT", "message": "Too many requests"}})
