import json
import os
import datetime as dt
from typing import Any, Dict, Optional

try:
    import redis  # type: ignore
except Exception:  # library may be missing in test env
    redis = None

_client: Any = None


class MemoryStore:
    def __init__(self):
        self.store: Dict[str, Any] = {}

    def set(self, key: str, value: Any, ex: Optional[int] = None):
        self.store[key] = value

    def get(self, key: str):
        return self.store.get(key)

    def hset(self, key: str, mapping: Dict[str, Any]):
        self.store.setdefault(key, {})
        self.store[key].update(mapping)

    def hgetall(self, key: str) -> Dict[str, Any]:
        return self.store.get(key, {})

    def incr(self, key: str) -> int:
        self.store[key] = int(self.store.get(key, 0)) + 1
        return self.store[key]

    def expire(self, key: str, ttl: int):
        return

    def ping(self):
        return True

    def flushdb(self):
        self.store.clear()


def get_client():
    global _client
    if _client is None:
        url = os.getenv("REDIS_URL", "memory://")
        if redis and not url.startswith("memory://"):
            ssl = url.startswith("rediss://")
            _client = redis.from_url(url, decode_responses=True, ssl=ssl)
        else:
            _client = MemoryStore()
    return _client


def get_json(key: str) -> Optional[Dict[str, Any]]:
    raw = get_client().get(key)
    return json.loads(raw) if raw else None


def set_json(key: str, value: Dict[str, Any], ttl: Optional[int] = None) -> None:
    data = json.dumps(value)
    client = get_client()
    client.set(key, data, ex=ttl)


def hgetall(key: str) -> Dict[str, Any]:
    return get_client().hgetall(key)


def hset(key: str, mapping: Dict[str, Any]) -> None:
    get_client().hset(key, mapping=mapping)


def touch_last_seen(user_id: str) -> None:
    now = dt.datetime.utcnow().isoformat()
    get_client().hset(f"user:{user_id}", mapping={"last_seen": now})


def ensure_indexes() -> None:
    return
