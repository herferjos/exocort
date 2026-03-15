"""HTTP-only OCR adapter around a generic vision endpoint."""

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
    read_list_str,
    read_str,
    resolve_api_key,
)
from engine.http import chat_completion
from engine.steps import (
    StepConfig,
    StepOutputConfig,
    extract_json_path,
    format_step_outputs,
    render_prompt,
)
from .base import OcrEngine
from .none import NullOcr

log = logging.getLogger("engine.ocr")


@dataclass(frozen=True)
class OcrConfig:
    format: str
    endpoint_url: str
    model: str | None
    api_key: str | None
    api_key_env: str | None
    api_key_header: str | None
    auth_scheme: str
    timeout_s: float
    languages: list[str]
    steps: list[StepConfig]
    output: StepOutputConfig | None


_ocr_engine: OcrEngine | None = None
_ocr_config: OcrConfig | None = None


def _load_config() -> OcrConfig:
    path = settings.ocr_config_path()
    data = load_json_config(path, "OCR")

    raw_format = (read_str(data, "format", None) or "openai").strip().lower()
    if raw_format == "none":
        return OcrConfig(
            format="none",
            endpoint_url="",
            model=None,
            api_key=None,
            api_key_env=None,
            api_key_header=None,
            auth_scheme="bearer",
            timeout_s=60.0,
            languages=["en", "es"],
            steps=[],
            output=None,
        )

    format_name = normalize_api_format(raw_format)
    endpoint_url = read_str(data, "endpoint_url", None)
    if not endpoint_url and format_name == "openai":
        base_url = read_str(data, "base_url", "https://api.openai.com/v1") or "https://api.openai.com/v1"
        endpoint_url = f"{base_url.rstrip('/')}/chat/completions"
    if not endpoint_url:
        raise ValueError("OCR config requires 'endpoint_url'")

    model = read_str(data, "model", None)
    api_key = read_str(data, "api_key", None)
    api_key_env = read_str(data, "api_key_env", None)
    api_key_header = read_str(data, "api_key_header", None)
    auth_scheme = (read_str(data, "auth_scheme", "bearer") or "bearer").lower()
    timeout_s = read_float(data, "timeout_s", 60.0)

    languages = read_list_str(data, "languages", ["en", "es"])
    if "languages" not in data:
        if "language" in data:
            languages = read_list_str(data, "language", ["en", "es"])
        elif "langs" in data:
            languages = read_list_str(data, "langs", ["en", "es"])
        elif "lang" in data:
            languages = read_list_str(data, "lang", ["en", "es"])

    steps: list[StepConfig] = []
    steps_raw = data.get("steps") or []
    if isinstance(steps_raw, list):
        for idx, raw in enumerate(steps_raw):
            if not isinstance(raw, dict):
                continue
            step_id = (
                read_str(raw, "id", None)
                or read_str(raw, "name", None)
                or f"step_{idx + 1}"
            )
            system_prompt = read_str(raw, "system_prompt", None) or read_str(
                raw, "system", None
            )
            user_prompt = (
                read_str(raw, "user_prompt", None)
                or read_str(raw, "prompt", None)
                or read_str(raw, "user", None)
            )
            response = (
                raw.get("response") if isinstance(raw.get("response"), dict) else {}
            )
            response_type = read_str(response, "type", "text") or "text"
            response_path = read_str(response, "path", None) or read_str(
                response, "field", None
            )
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
        raw_separator = output_raw.get("separator")
        separator = raw_separator if isinstance(raw_separator, str) else "\n\n"
        raw_label_format = output_raw.get("label_format")
        label_format = (
            raw_label_format
            if isinstance(raw_label_format, str) and raw_label_format
            else "{id}:\n{value}"
        )
        output_cfg = StepOutputConfig(
            mode=mode,
            steps=output_steps or None,
            separator=separator,
            label_format=label_format,
        )

    return OcrConfig(
        format=format_name,
        endpoint_url=endpoint_url,
        model=model,
        api_key=api_key,
        api_key_env=api_key_env,
        api_key_header=api_key_header,
        auth_scheme=auth_scheme,
        timeout_s=timeout_s,
        languages=languages,
        steps=steps,
        output=output_cfg,
    )


def get_ocr_config() -> OcrConfig:
    global _ocr_config
    if _ocr_config is None:
        _ocr_config = _load_config()
    return _ocr_config


class HttpOcrEngine(OcrEngine):
    def __init__(self, cfg: OcrConfig):
        self._cfg = cfg

    def _run_single_step(self, step: StepConfig, image_path: Path, context: dict[str, str]) -> str:
        cfg = self._cfg
        api_key = resolve_api_key(cfg.api_key, cfg.api_key_env, None)
        if not api_key and cfg.format in {"openai", "anthropic"}:
            raise ValueError("OCR config requires an API key via 'api_key' or 'api_key_env'")

        headers = build_http_headers(
            format_name=cfg.format,
            api_key=api_key,
            headers=None,
            api_key_header=cfg.api_key_header,
            auth_scheme=cfg.auth_scheme,
        )

        system_prompt = render_prompt(step.system_prompt, context).strip() if step.system_prompt else ""
        user_prompt = render_prompt(step.user_prompt, context).strip() if step.user_prompt else ""

        text = chat_completion(
            endpoint_url=cfg.endpoint_url,
            format_name=cfg.format,
            model=cfg.model,
            api_key=api_key,
            headers=headers,
            api_key_header=cfg.api_key_header,
            auth_scheme=cfg.auth_scheme,
            anthropic_version=None,
            system=system_prompt,
            user=user_prompt,
            timeout_s=cfg.timeout_s,
            temperature=step.temperature,
            max_tokens=step.max_tokens,
            image_path=image_path,
            audio_path=None,
            audio_mime_type=None,
            output_model=None,
        )

        if (step.response_type or "").lower() != "json":
            return text

        try:
            import json

            payload = json.loads(text)
        except Exception:
            return text
        extracted = extract_json_path(payload, step.response_path)
        if extracted is None:
            return text
        if isinstance(extracted, str):
            return extracted.strip()
        import json as _json

        return _json.dumps(extracted, ensure_ascii=False)

    def extract_text(self, path: Path) -> str:
        cfg = self._cfg
        if not cfg.steps:
            # Simple one-shot OCR with a generic instruction
            dummy_step = StepConfig(
                step_id="ocr",
                system_prompt="You are an OCR engine. Extract plain text from the image.",
                user_prompt="Read the text in the image and return it as plain text.",
                response_type="text",
                response_path=None,
                temperature=None,
                max_tokens=None,
            )
            return self._run_single_step(dummy_step, path, {})

        results: list[tuple[str, str]] = []
        context: dict[str, str] = {}
        for step in cfg.steps:
            text = self._run_single_step(step, path, context)
            results.append((step.step_id, text))
            context["prev"] = text
            context[step.step_id] = text
        return format_step_outputs(results, cfg.output)


def get_ocr_engine() -> OcrEngine:
    global _ocr_engine
    if _ocr_engine is not None:
        return _ocr_engine

    cfg = get_ocr_config()
    if cfg.format == "none":
        _ocr_engine = NullOcr()
    else:
        _ocr_engine = HttpOcrEngine(cfg)

    return _ocr_engine
