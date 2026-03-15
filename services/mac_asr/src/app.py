from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from .asr import ensure_speech_permission, transcribe_audio_file


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


def _env_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip()


@dataclass(frozen=True)
class ServiceConfig:
    transcription_timeout_s: float
    prompt_permission: bool
    locale: str


def build_config() -> ServiceConfig:
    return ServiceConfig(
        transcription_timeout_s=max(
            3.0, _env_float("MAC_ASR_TRANSCRIPTION_TIMEOUT_S", 30.0)
        ),
        prompt_permission=_env_bool("MAC_ASR_PROMPT_PERMISSION", True),
        locale=_env_str("MAC_ASR_LOCALE", "es-ES"),
    )


logging.basicConfig(
    level=getattr(logging, _env_str("MAC_ASR_LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(message)s",
)

app = FastAPI(title="Mac ASR Service", version="0.1.0")


def _ensure_permission(config: ServiceConfig) -> None:
    if not ensure_speech_permission(prompt=config.prompt_permission):
        raise HTTPException(
            status_code=409,
            detail="Speech recognition permission is required for mac_asr.",
        )


@app.get("/health")
def health() -> dict[str, object]:
    config = build_config()
    return {
        "ok": True,
        "locale": config.locale,
        "speech_permission": ensure_speech_permission(prompt=False),
    }


@app.get("/status")
def status() -> dict[str, object]:
    config = build_config()
    return {
        "locale": config.locale,
        "transcription_timeout_s": config.transcription_timeout_s,
        "speech_permission": ensure_speech_permission(prompt=False),
    }


@app.post("/v1/audio/transcriptions")
async def transcribe_audio(
    file: UploadFile = File(...),
    model_name: Annotated[str | None, Form()] = None,
    language: Annotated[str | None, Form()] = None,
    prompt: Annotated[str | None, Form()] = None,
) -> dict[str, object]:
    del model_name, prompt

    config = build_config()
    _ensure_permission(config)

    suffix = Path(file.filename or "audio.wav").suffix or ".wav"
    with NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)

    try:
        tmp_path.write_bytes(await file.read())
        transcription = transcribe_audio_file(
            tmp_path,
            locale=(language or config.locale),
            timeout_s=config.transcription_timeout_s,
        )
        return transcription.to_dict()
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


def main() -> None:
    import uvicorn

    config = build_config()
    if not ensure_speech_permission(prompt=config.prompt_permission):
        raise RuntimeError("Speech recognition permission is required for mac_asr.")

    host = _env_str("MAC_ASR_HOST", "127.0.0.1")
    port = int(_env_float("MAC_ASR_PORT", 9092))
    uvicorn.run("src.app:app", host=host, port=port, reload=False)
