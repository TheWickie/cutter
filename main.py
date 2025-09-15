import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

try:
    from loguru import logger
except Exception:  # fallback when loguru is unavailable
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("cutter")


def create_app() -> FastAPI:
    load_dotenv()
    if hasattr(logger, "remove"):
        logger.remove()
        logger.add(lambda msg: print(msg, end=""), level=os.getenv("LOG_LEVEL", "INFO"))

    app = FastAPI(title="Cutter", version="2.0.0")
    origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from core.redis_store import get_client, ensure_indexes
    from core.guardrails import load_policy

    @app.on_event("startup")
    async def startup() -> None:
        get_client()
        ensure_indexes()
        load_policy()

    from routes import auth, chat, voice, memory, system

    app.include_router(auth.router)
    app.include_router(chat.router)
    app.include_router(voice.router)
    app.include_router(memory.router)
    app.include_router(system.router)

    return app


app = create_app()
