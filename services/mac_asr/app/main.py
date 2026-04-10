from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from app.api.v1.api import api_router
from src.asr import ensure_speech_permission
from src.config import load_settings

app = FastAPI(title="Mac ASR", version="0.1.0")
app.include_router(api_router)


def main() -> None:
    settings = load_settings()
    if not ensure_speech_permission(prompt=settings.prompt_permission):
        raise RuntimeError("Speech recognition permission is required.")
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level,
    )
