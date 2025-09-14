import os
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
os.environ["REDIS_URL"] = "fakeredis://"

from fastapi.testclient import TestClient
from main import app


def test_guardrails():
    with TestClient(app) as client:
        resp = client.get("/v2/guardrails")
        assert "policy" in resp.json()
