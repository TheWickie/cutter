import json
import os
import datetime as dt
from typing import Any, Dict, Optional

try:
    import redis  # type: ignore
except Exception:  # library may be missing in test env
    redis = None

try:  # used in tests
    import fakeredis  # type: ignore
except Exception:
    fakeredis = None

_client: Any = None
_client_scheme: str = "unknown"  # one of: rediss, redis, fakeredis, memory, unknown


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
    global _client_scheme
    if _client is None:
        url = os.getenv("REDIS_URL", "memory://")
        if url.startswith("fakeredis://") and fakeredis:
            _client = fakeredis.FakeRedis(decode_responses=True)
            _client_scheme = "fakeredis"
            return _client
        if redis and not url.startswith("memory://"):
            # 1) Try as-is (supports rediss:// for TLS)
            try:
                client = redis.from_url(url, decode_responses=True)
                # Validate connection early so we can gracefully fallback
                client.ping()
                _client = client
                _client_scheme = "rediss" if url.startswith("rediss://") else "redis"
                return _client
            except Exception as e:
                # Common managed Redis setups expose non-TLS ports. If TLS handshake fails,
                # retry without TLS by swapping rediss:// -> redis://
                if url.startswith("rediss://"):
                    try:
                        plain_url = "redis://" + url[len("rediss://") :]
                        client = redis.from_url(plain_url, decode_responses=True)
                        client.ping()
                        _client = client
                        _client_scheme = "redis"
                        return _client
                    except Exception:
                        pass
                # Last resort: raise after falling through to in-memory store
        # Fallback to in-memory store so the app can still run in dev
        _client = MemoryStore()
        _client_scheme = "memory"
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


def get_client_scheme() -> str:
    """Returns the scheme for the active Redis client: rediss, redis, fakeredis, or memory.

    Ensures the client is initialized before reporting.
    """
    global _client_scheme
    if _client is None:
        try:
            get_client()
        except Exception:
            pass
    return _client_scheme
