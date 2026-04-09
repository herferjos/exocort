from __future__ import annotations

from fastapi import APIRouter

from src.asr import ensure_speech_permission
from src.config import load_settings

router = APIRouter()


@router.get("/health")
def health() -> dict[str, object]:
    settings = load_settings()
    return {
        "ok": True,
        "locale": settings.locale.strip() or None,
        "speech_permission": ensure_speech_permission(prompt=False),
    }
