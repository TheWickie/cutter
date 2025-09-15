import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

try:
    from loguru import logger
except Exception:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("cutter")

def create_app() -> FastAPI:
    load_dotenv()

    app = FastAPI(title="Cutter Backend", version="1.0.0")

    # CORS
    default_origins = [
        "https://addiction.needssomehelp.com",
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8000",
    ]
    env_origins = os.getenv("ALLOWED_ORIGINS")
    origins = [o.strip() for o in env_origins.split(",")] if env_origins else default_origins

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "OpenAI-Beta"],
        max_age=600,
    )

    from core.redis_store import get_client, ensure_indexes
    from core.guardrails import load_policy

    @app.on_event("startup")
    async def startup() -> None:
        get_client()
        ensure_indexes()
        load_policy()

    # Include routes
    from routes import auth, chat, voice, memory, system
    app.include_router(auth.router)
    app.include_router(chat.router)
    app.include_router(voice.router)
    app.include_router(memory.router)
    app.include_router(system.router)

    logger.info("Cutter app ready. Allowed origins: %s", origins)
    return app

app = create_app()
