from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from app.api.v1.api import api_router
from src.chat.service import startup
from common.utils.logs import get_logger
from src.config.settings import load_settings

app = FastAPI(title="Llama.cpp", version="0.1.0")
app.add_event_handler("startup", startup)
app.include_router(api_router)
log = get_logger("llama_cpp", "app")


def main() -> None:
    settings = load_settings()
    log.info(
        "Starting llama.cpp app | host=%s | port=%s | reload=%s | log_level=%s",
        settings.host,
        settings.port,
        settings.reload,
        settings.log_level,
    )
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level,
    )
