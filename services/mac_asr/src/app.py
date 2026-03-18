from __future__ import annotations

import logging
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from starlette.responses import Response

from .asr import (
    _is_no_speech_error,
    ensure_speech_permission,
    resolve_locale,
    transcribe_audio_file,
)
from .config import HOST, LOCALE, PORT, PROMPT_PERMISSION, TRANSCRIPTION_TIMEOUT_S
from .lang_detect import detect_language

log = logging.getLogger("mac_asr")

app = FastAPI(title="Mac ASR", version="0.1.0")


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "ok": True,
        "locale": (LOCALE or "").strip() or None,
        "speech_permission": ensure_speech_permission(prompt=False),
    }


@app.post("/v1/audio/transcriptions", response_model=None)
async def transcribe_audio(
    file: UploadFile = File(...),
    language: Annotated[str | None, Form()] = None,
) -> object:
    if not ensure_speech_permission(prompt=PROMPT_PERMISSION):
        raise HTTPException(
            status_code=409,
            detail="Speech recognition permission is required.",
        )

    suffix = Path(file.filename or "audio.wav").suffix or ".wav"
    with NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        path = Path(tmp.name)
    try:
        path.write_bytes(await file.read())
        explicit_language = (language or "").strip()
        detect_requested = (
            (explicit_language.lower() == "auto")
            or ((LOCALE or "").strip().lower() == "auto")
        )
        if explicit_language.lower() == "auto":
            explicit_language = ""
        detected_code = None
        if not explicit_language and detect_requested:
            detected_code, _ = detect_language(path)
        locale = resolve_locale(detected_code, explicit_language)
        try:
            result = transcribe_audio_file(
                path,
                locale=locale,
                timeout_s=TRANSCRIPTION_TIMEOUT_S,
            )
            payload = result.to_dict()
            if not str(payload.get("text") or "").strip():
                log.info(
                    "Empty transcription | locale=%s | file=%s",
                    locale,
                    file.filename,
                )
                return Response(status_code=204)
            return payload
        except RuntimeError as e:
            if _is_no_speech_error(str(e)):
                log.info(
                    "No speech detected | locale=%s | file=%s",
                    locale,
                    file.filename,
                )
                return Response(status_code=204)
            raise
    finally:
        path.unlink(missing_ok=True)


def main() -> None:
    import uvicorn
    if not ensure_speech_permission(prompt=PROMPT_PERMISSION):
        raise RuntimeError("Speech recognition permission is required.")
    uvicorn.run("src.app:app", host=HOST, port=PORT, reload=False)
