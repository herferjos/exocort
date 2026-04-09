from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from app.api.v1.api import api_router
from src.config import load_settings

app = FastAPI(title="Faster Whisper", version="0.1.0")
app.include_router(api_router)


def main() -> None:
    settings = load_settings()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
