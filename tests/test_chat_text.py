import os
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


def create_session():
    client.post("/v2/auth/call", json={"number": "123"})
    resp = client.post(
        "/v2/auth/verify-name", json={"number": "123", "name": "Alice A"}
    )
    data = resp.json()
    return data["session_id"], data["user_id"]


def test_chat_text():
    session_id, user_id = create_session()
    resp = client.post(
        "/v2/chat/send", json={"session_id": session_id, "message": "hello"}
    )
    assert resp.status_code == 200
    resp = client.post(
        "/v2/chat/send", json={"session_id": session_id, "message": "second"}
    )
    assert resp.status_code == 200
    mem = get_client().get(f"memory:{user_id}")
    assert mem is not None
