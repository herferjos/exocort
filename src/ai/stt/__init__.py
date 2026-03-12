"""STT module with pluggable providers and JSON config."""
import logging
from dataclasses import dataclass

import settings
from ai.config import load_json_config, read_bool, read_float, read_int, read_list_str, read_str
from ai.steps import StepConfig, StepOutputConfig
from .base import SpeechTranscriber
from .faster_whisper import FasterWhisperTranscriber
from .gemini import GeminiTranscriber
from .none import NullTranscriber
from .openai import OpenAITranscriber

log = logging.getLogger("ai.stt")


@dataclass(frozen=True)
class SttConfig:
    provider: str
    model: str | None
    language: str | None
    device: str
    compute_type: str
    vad_filter: bool
    base_url: str | None
    api_key: str | None
    api_key_env: str | None
    steps: list[StepConfig]
    output: StepOutputConfig | None


_transcriber: SpeechTranscriber | None = None
_stt_config: SttConfig | None = None


def _load_config() -> SttConfig:
    path = settings.stt_config_path()
    data = load_json_config(path, "STT")

    provider = (read_str(data, "provider", "faster_whisper") or "faster_whisper").lower()
    model = read_str(data, "model", None)
    language = read_str(data, "language", None)
    if "language" not in data and "lang" in data:
        language = read_str(data, "lang", None)

    device = read_str(data, "device", "cpu") or "cpu"
    compute_type = read_str(data, "compute_type", "int8") or "int8"
    vad_filter = read_bool(data, "vad_filter", True)

    base_url = read_str(data, "base_url", None)
    api_key = read_str(data, "api_key", None)
    api_key_env = read_str(data, "api_key_env", None)

    steps: list[StepConfig] = []
    steps_raw = data.get("steps") or []
    if isinstance(steps_raw, list):
        for idx, raw in enumerate(steps_raw):
            if not isinstance(raw, dict):
                continue
            step_id = read_str(raw, "id", None) or read_str(raw, "name", None) or f"step_{idx + 1}"
            system_prompt = read_str(raw, "system_prompt", None) or read_str(raw, "system", None)
            user_prompt = (
                read_str(raw, "user_prompt", None)
                or read_str(raw, "prompt", None)
                or read_str(raw, "user", None)
            )
            response = raw.get("response") if isinstance(raw.get("response"), dict) else {}
            response_type = read_str(response, "type", "text") or "text"
            response_path = read_str(response, "path", None) or read_str(response, "field", None)
            temperature = None
            if raw.get("temperature") is not None:
                temperature = read_float(raw, "temperature", 0.0)
            max_tokens = None
            if raw.get("max_tokens") is not None:
                max_tokens = read_int(raw, "max_tokens", 0)
            elif raw.get("max_output_tokens") is not None:
                max_tokens = read_int(raw, "max_output_tokens", 0)
            steps.append(
                StepConfig(
                    step_id=str(step_id),
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_type=response_type,
                    response_path=response_path,
                    temperature=temperature,
                    max_tokens=max_tokens if max_tokens and max_tokens > 0 else None,
                )
            )

    output_cfg: StepOutputConfig | None = None
    output_raw = data.get("output") if isinstance(data.get("output"), dict) else None
    if output_raw is not None:
        mode = (read_str(output_raw, "mode", "first") or "first").lower()
        output_steps = read_list_str(output_raw, "steps", [])
        separator = read_str(output_raw, "separator", "\n\n") or "\n\n"
        label_format = read_str(output_raw, "label_format", "{id}:\n{value}") or "{id}:\n{value}"
        output_cfg = StepOutputConfig(
            mode=mode,
            steps=output_steps or None,
            separator=separator,
            label_format=label_format,
        )

    return SttConfig(
        provider=provider,
        model=model,
        language=language,
        device=device,
        compute_type=compute_type,
        vad_filter=vad_filter,
        base_url=base_url,
        api_key=api_key,
        api_key_env=api_key_env,
        steps=steps,
        output=output_cfg,
    )


def get_stt_config() -> SttConfig:
    global _stt_config
    if _stt_config is None:
        _stt_config = _load_config()
    return _stt_config


def get_transcriber() -> SpeechTranscriber:
    global _transcriber
    if _transcriber is not None:
        return _transcriber

    cfg = get_stt_config()
    provider = cfg.provider

    if provider == "none":
        _transcriber = NullTranscriber()
    elif provider == "faster_whisper":
        model = cfg.model or "small"
        if cfg.steps:
            log.warning("STT steps are not supported for faster_whisper; ignoring steps.")
        _transcriber = FasterWhisperTranscriber(
            model=model,
            device=cfg.device,
            compute_type=cfg.compute_type,
            language=cfg.language,
            vad_filter=cfg.vad_filter,
        )
    elif provider in {"openai", "lmstudio", "openai_compat", "local_openai"}:
        model = cfg.model or "gpt-4o-mini-transcribe"
        _transcriber = OpenAITranscriber(
            model=model,
            api_key=cfg.api_key,
            api_key_env=cfg.api_key_env,
            base_url=cfg.base_url,
            steps=cfg.steps,
            output=cfg.output,
        )
    elif provider == "gemini":
        model = cfg.model or "gemini-3.1-flash-lite-preview"
        _transcriber = GeminiTranscriber(
            model=model,
            api_key=cfg.api_key,
            api_key_env=cfg.api_key_env,
            steps=cfg.steps,
            output=cfg.output,
        )
    else:
        raise ValueError(f"Unknown STT provider: {provider}")

    return _transcriber
