import os
from fastapi.testclient import TestClient
from main import app


def test_health_endpoint(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    client = TestClient(app)
    resp = client.get("/v2/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "redis_ok" in data
    assert "openai_realtime_ok" in data
    assert data["openai_realtime_ok"] is False
    assert data["model"]
    assert "rate_limit_per_minute" in data
