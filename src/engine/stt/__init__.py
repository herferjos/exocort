"""HTTP-only STT adapter around a generic transcription endpoint."""

import logging
from dataclasses import dataclass
from pathlib import Path

import settings
from engine.config import (
    build_http_headers,
    load_json_config,
    normalize_api_format,
    read_float,
    read_int,
    read_str,
    resolve_api_key,
)
from .base import SpeechTranscriber

log = logging.getLogger("engine.stt")


@dataclass(frozen=True)
class SttConfig:
    format: str
    endpoint_url: str
    model: str | None
    api_key: str | None
    api_key_env: str | None
    api_key_header: str | None
    auth_scheme: str
    timeout_s: float
    language: str | None
    steps: list[dict]
    output: str


_transcriber: SpeechTranscriber | None = None
_stt_config: SttConfig | None = None


def _load_config() -> SttConfig:
    path = settings.stt_config_path()
    data = load_json_config(path, "STT")

    raw_format = (read_str(data, "format", None) or "openai").strip().lower()
    if raw_format == "none":
        return SttConfig(
            format="none",
            endpoint_url="",
            model=None,
            api_key=None,
            api_key_env=None,
            api_key_header=None,
            auth_scheme="bearer",
            timeout_s=60.0,
            language=None,
            steps=[],
            output="text",
        )

    format_name = normalize_api_format(raw_format)
    endpoint_url = read_str(data, "endpoint_url", None)
    if not endpoint_url and format_name == "openai":
        base_url = read_str(data, "base_url", "https://api.openai.com/v1") or "https://api.openai.com/v1"
        endpoint_url = f"{base_url.rstrip('/')}/audio/transcriptions"
    if not endpoint_url:
        raise ValueError("STT config requires 'endpoint_url'")

    model = read_str(data, "model", None)
    api_key = read_str(data, "api_key", None)
    api_key_env = read_str(data, "api_key_env", None)
    api_key_header = read_str(data, "api_key_header", None)
    auth_scheme = (read_str(data, "auth_scheme", "bearer") or "bearer").lower()
    timeout_s = read_float(data, "timeout_s", 60.0)
    language = read_str(data, "language", None)

    steps_raw = data.get("steps") or []
    steps: list[dict] = steps_raw if isinstance(steps_raw, list) else []
    output = read_str(data, "output", "text") or "text"

    return SttConfig(
        format=format_name,
        endpoint_url=endpoint_url,
        model=model,
        api_key=api_key,
        api_key_env=api_key_env,
        api_key_header=api_key_header,
        auth_scheme=auth_scheme,
        timeout_s=timeout_s,
        language=language,
        steps=steps,
        output=output,
    )


def get_stt_config() -> SttConfig:
    global _stt_config
    if _stt_config is None:
        _stt_config = _load_config()
    return _stt_config


class HttpSpeechTranscriber(SpeechTranscriber):
    def __init__(self, cfg: SttConfig):
        self._cfg = cfg

    def transcribe(self, path: Path, mime_type: str | None = None) -> str:
        cfg = self._cfg
        if cfg.format != "openai":
            raise ValueError("Only 'openai' format STT is supported for now")

        api_key = resolve_api_key(cfg.api_key, cfg.api_key_env, None)
        if not api_key:
            raise ValueError("STT config requires an API key via 'api_key' or 'api_key_env'")

        headers = build_http_headers(
            format_name="openai",
            api_key=api_key,
            headers=None,
            api_key_header=cfg.api_key_header,
            auth_scheme=cfg.auth_scheme,
        )
        headers.pop("content-type", None)

        from engine.http import openai_transcription

        return openai_transcription(
            endpoint_url=cfg.endpoint_url,
            model=cfg.model,
            api_key=api_key,
            headers=None,
            api_key_header=cfg.api_key_header,
            auth_scheme=cfg.auth_scheme,
            file_path=path,
            timeout_s=cfg.timeout_s,
            prompt=None,
            language=cfg.language,
        )


def get_transcriber() -> SpeechTranscriber:
    global _transcriber
    if _transcriber is None:
        cfg = get_stt_config()
        if cfg.format == "none":
            from .none import NullTranscriber

            _transcriber = NullTranscriber()
        else:
            _transcriber = HttpSpeechTranscriber(cfg)
    return _transcriber
