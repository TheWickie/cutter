import os
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
os.environ["REDIS_URL"] = "fakeredis://"
os.environ["RATE_LIMIT_PER_MINUTE"] = "100"

from fastapi.testclient import TestClient
from main import app
from core.redis_store import get_client

client = TestClient(app)


def setup_function() -> None:
    get_client().flushdb()


def test_auth_flow():
    resp = client.post("/v2/auth/call", json={"number": "123"})
    assert resp.status_code == 200
    assert resp.json()["need_name_registration"] is True
    resp = client.post(
        "/v2/auth/verify-name",
        json={"number": "123", "name": "Alice A"},
    )
    data = resp.json()
    assert "session_id" in data
    r = get_client()
    user = r.hgetall(f"user:{data['user_id']}")
    assert user.get("authed") == "1"
