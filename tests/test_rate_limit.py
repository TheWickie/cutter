import os
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
os.environ["REDIS_URL"] = "fakeredis://"

from fastapi.testclient import TestClient
from main import app
from core.redis_store import get_client
import core.rate_limit as rl


def test_rate_limit():
    rl.RATE_LIMIT_PER_MINUTE = 2
    with TestClient(app) as client:
        get_client().flushdb()
        for _ in range(2):
            client.post("/v2/auth/call", json={"number": "1"})
        resp = client.post("/v2/auth/call", json={"number": "1"})
        assert resp.status_code == 429
