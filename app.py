"""WSGI/ASGI entrypoint for Render expecting module `app`.
This file re-exports the FastAPI `app` from `main.py`.
"""

from main import app  # noqa: F401
