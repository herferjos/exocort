from __future__ import annotations

import logging
from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from starlette.responses import Response

from src.asr import (
    _is_no_speech_error,
    ensure_speech_permission,
    transcribe_audio_file,
)
from src.config import load_settings
from src.transcription import resolve_request_locale, transcription_text

log = logging.getLogger("mac_asr")

router = APIRouter()


@router.post("/v1/audio/transcriptions", response_model=None)
async def transcribe_audio(
    file: UploadFile = File(...),
    model: str | None = Form(None),
    language: str | None = Form(None),
    prompt: str | None = Form(None),
    response_format: str | None = Form(None),
    temperature: float | None = Form(None),
) -> object:
    settings = load_settings()
    if not ensure_speech_permission(prompt=settings.prompt_permission):
        raise HTTPException(
            status_code=409,
            detail="Speech recognition permission is required.",
        )

    path = Path(gettempdir()) / f"{uuid4().hex}.wav"
    try:
        path.write_bytes(await file.read())
        locale = resolve_request_locale(path, language)
        if not locale:
            return Response(status_code=204)
        try:
            result = transcribe_audio_file(
                path,
                locale=locale,
                timeout_s=settings.transcription_timeout_s,
            )
            text = transcription_text(result)
            if not text:
                log.info(
                    "Empty transcription | locale=%s | file=%s",
                    locale,
                    file.filename,
                )
                return Response(status_code=204)
            return {
                "text": text,
                "task": "transcribe",
                "language": locale,
                "duration": None,
            }
        except RuntimeError as exc:
            if _is_no_speech_error(str(exc)):
                log.info(
                    "No speech detected | locale=%s | file=%s",
                    locale,
                    file.filename,
                )
                return Response(status_code=204)
            raise
    finally:
        path.unlink(missing_ok=True)
