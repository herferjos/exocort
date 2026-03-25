from __future__ import annotations

import logging
from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4

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


def _resolve_request_locale(path: Path, language: str | None) -> str:
    explicit_language = (language or "").strip()
    explicit_language_lower = explicit_language.lower()
    detect_requested = (
        explicit_language_lower == "auto" or ((LOCALE or "").strip().lower() == "auto")
    )
    if explicit_language_lower == "auto":
        explicit_language = ""
    detected_code = None
    if not explicit_language and detect_requested:
        detected_code, _ = detect_language(path)
    return resolve_locale(detected_code, explicit_language)


def _transcription_text(result: object) -> str:
    text = str(getattr(result, "text", "") or "").strip()
    if not text and hasattr(result, "to_dict"):
        text = str(result.to_dict().get("text", "") or "").strip()
    return text


@app.post("/v1/audio/transcriptions", response_model=None)
async def transcribe_audio(
    file: UploadFile = File(...),
    model: str | None = Form(None),
    language: str | None = Form(None),
    prompt: str | None = Form(None),
) -> object:
    del model, prompt
    if not ensure_speech_permission(prompt=PROMPT_PERMISSION):
        raise HTTPException(
            status_code=409,
            detail="Speech recognition permission is required.",
        )

    path = Path(gettempdir()) / f"{uuid4().hex}.wav"
    try:
        path.write_bytes(await file.read())
        locale = _resolve_request_locale(path, language)
        try:
            result = transcribe_audio_file(
                path,
                locale=locale,
                timeout_s=TRANSCRIPTION_TIMEOUT_S,
            )
            text = _transcription_text(result)
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


def main() -> None:
    import uvicorn
    if not ensure_speech_permission(prompt=PROMPT_PERMISSION):
        raise RuntimeError("Speech recognition permission is required.")
    uvicorn.run("src.app:app", host=HOST, port=PORT, reload=True)
