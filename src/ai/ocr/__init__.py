"""OCR module with pluggable providers and JSON config."""
import logging
from dataclasses import dataclass

import settings
from ai.config import load_json_config, read_bool, read_float, read_int, read_list_str, read_str
from ai.steps import StepConfig, StepOutputConfig
from .base import OcrEngine
from .gemini import GeminiOcrEngine
from .llama_cpp import LlamaCppOcrEngine
from .none import NullOcr
from .openai import OpenAIOcrEngine
from .paddle import PaddleOcrEngine

log = logging.getLogger("ai.ocr")


@dataclass(frozen=True)
class OcrConfig:
    provider: str
    model: str | None
    languages: list[str]
    base_url: str | None
    api_key: str | None
    api_key_env: str | None
    steps: list[StepConfig]
    output: StepOutputConfig | None
    model_path: str | None
    context_length: int
    n_gpu_layers: int
    threads: int
    batch_size: int
    flash_attention: bool
    use_mmap: bool
    offload_kqv: bool
    seed: int | None
    chat_format: str | None
    chat_template: str | None
    clip_model_path: str | None


_ocr_engine: OcrEngine | None = None
_ocr_config: OcrConfig | None = None


def _load_config() -> OcrConfig:
    path = settings.ocr_config_path()
    data = load_json_config(path, "OCR")

    provider = (read_str(data, "provider", "paddle") or "paddle").lower()
    model = read_str(data, "model", None)
    base_url = read_str(data, "base_url", None)
    api_key = read_str(data, "api_key", None)
    api_key_env = read_str(data, "api_key_env", None)

    model_path = read_str(data, "model_path", None) or read_str(data, "modelPath", None)
    context_length = read_int(data, "context_length", 4096)
    n_gpu_layers = read_int(data, "n_gpu_layers", -1)
    threads = read_int(data, "threads", 4)
    batch_size = read_int(data, "batch_size", 512)
    flash_attention = read_bool(data, "flash_attention", False)
    use_mmap = read_bool(data, "use_mmap", True)
    offload_kqv = read_bool(data, "offload_kqv", False)
    seed = None
    if "seed" in data and data.get("seed") not in (None, ""):
        try:
            seed = int(data.get("seed"))
        except (TypeError, ValueError):
            seed = None
    chat_format = read_str(data, "chat_format", None)
    chat_template = read_str(data, "chat_template", None)
    chat_template_path = read_str(data, "chat_template_path", None)
    if chat_template_path:
        template_path = (path.parent / chat_template_path).expanduser().resolve()
        if not template_path.exists():
            raise FileNotFoundError(f"OCR chat_template_path not found: {template_path}")
        chat_template = template_path.read_text(encoding="utf-8")

    clip_model_path = read_str(data, "clip_model_path", None) or read_str(data, "mmproj_path", None)

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

    return OcrConfig(
        provider=provider,
        model=model,
        languages=languages,
        base_url=base_url,
        api_key=api_key,
        api_key_env=api_key_env,
        steps=steps,
        output=output_cfg,
        model_path=model_path,
        context_length=context_length,
        n_gpu_layers=n_gpu_layers,
        threads=threads,
        batch_size=batch_size,
        flash_attention=flash_attention,
        use_mmap=use_mmap,
        offload_kqv=offload_kqv,
        seed=seed,
        chat_format=chat_format,
        chat_template=chat_template,
        clip_model_path=clip_model_path,
    )


def get_ocr_config() -> OcrConfig:
    global _ocr_config
    if _ocr_config is None:
        _ocr_config = _load_config()
    return _ocr_config


def get_ocr_engine() -> OcrEngine:
    global _ocr_engine
    if _ocr_engine is not None:
        return _ocr_engine

    cfg = get_ocr_config()
    provider = cfg.provider

    if provider == "none":
        _ocr_engine = NullOcr()
    elif provider == "paddle":
        if cfg.steps:
            log.warning("OCR steps are not supported for paddle; ignoring steps.")
        _ocr_engine = PaddleOcrEngine(cfg.languages)
    elif provider in {"openai", "lmstudio", "openai_compat", "local_openai"}:
        model = cfg.model or "gpt-4o-mini"
        _ocr_engine = OpenAIOcrEngine(
            model=model,
            api_key=cfg.api_key,
            api_key_env=cfg.api_key_env,
            base_url=cfg.base_url,
            steps=cfg.steps,
            output=cfg.output,
        )
    elif provider == "llama_cpp":
        if not cfg.clip_model_path:
            raise ValueError(
                "OCR llama_cpp requires 'clip_model_path' (mmproj) for vision. "
                "Set clip_model_path in ocr.json."
            )
        _ocr_engine = LlamaCppOcrEngine(
            model_path=cfg.model_path or "",
            context_length=cfg.context_length,
            n_gpu_layers=cfg.n_gpu_layers,
            threads=cfg.threads,
            batch_size=cfg.batch_size,
            flash_attention=cfg.flash_attention,
            use_mmap=cfg.use_mmap,
            offload_kqv=cfg.offload_kqv,
            seed=cfg.seed,
            chat_format=cfg.chat_format,
            chat_template=cfg.chat_template,
            clip_model_path=cfg.clip_model_path,
            steps=cfg.steps,
            output=cfg.output,
        )
    elif provider == "gemini":
        model = cfg.model or "gemini-3.1-flash-lite-preview"
        _ocr_engine = GeminiOcrEngine(
            model=model,
            api_key=cfg.api_key,
            api_key_env=cfg.api_key_env,
            steps=cfg.steps,
            output=cfg.output,
        )
    else:
        raise ValueError(f"Unknown OCR provider: {provider}")

    return _ocr_engine
