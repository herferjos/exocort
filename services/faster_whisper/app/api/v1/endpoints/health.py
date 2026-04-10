from __future__ import annotations

from fastapi import APIRouter

from common.models.health import HealthResponse
from src.transcription import health as transcription_health

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return transcription_health()
