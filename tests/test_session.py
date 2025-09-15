import sys, pathlib, os
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
os.environ["REDIS_URL"] = "fakeredis://"
os.environ["OPENAI_API_KEY"] = ""

from fastapi.testclient import TestClient
from main import app
from core.redis_store import get_client
import core.rate_limit as rl
import routes.system as system


def test_session_returns_token():
    rl.RATE_LIMIT_PER_MINUTE = 1000
    system.OPENAI_API_KEY = ""
    with TestClient(app) as client:
        get_client().flushdb()
        resp = client.post("/session")
    assert resp.status_code == 200
    data = resp.json()
    assert "client_secret" in data
    assert "model" in data
    assert data["client_secret"]


def test_session_parses_nested_client_secret(monkeypatch):
    rl.RATE_LIMIT_PER_MINUTE = 1000
    system.OPENAI_API_KEY = "sk-test"

    class FakeResp:
        status_code = 200

        def json(self):
            return {
                "client_secret": {"value": "secret-token"},
                "model": "gpt-test",
            }

    def fake_post(*args, **kwargs):
        return FakeResp()

    monkeypatch.setattr(system.httpx, "post", fake_post)
    with TestClient(app) as client:
        get_client().flushdb()
        resp = client.post("/session")
    assert resp.status_code == 200
    data = resp.json()
    assert data["client_secret"] == "secret-token"
    assert data["model"] == "gpt-test"
