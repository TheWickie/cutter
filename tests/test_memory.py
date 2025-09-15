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


def create_user():
    client.post("/v2/auth/call", json={"number": "123"})
    resp = client.post(
        "/v2/auth/verify-name", json={"number": "123", "name": "Alice A"}
    )
    return resp.json()


def test_profile_and_notes():
    data = create_user()
    uid = data["user_id"]
    resp = client.patch(
        "/v2/memory/profile",
        json={"user_id": uid, "patch": {"preferences": "evening"}},
    )
    assert resp.json()["profile"]["preferences"] == "evening"
    resp = client.post("/v2/memory/notes", json={"user_id": uid, "note": "test note"})
    assert resp.json()["status"] == "ok"
    resp = client.get(f"/v2/memory/notes?user_id={uid}")
    assert len(resp.json()["notes"]) == 1
