from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from common.utils.yaml import load_yaml_config, resolve_config_path

from .models import LlamaCppSettings


def _config_path() -> Path:
    override = os.environ.get("EXOCORT_CONFIG_PATH")
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parents[2] / "config.yaml"


def _load_chat_template(config_dir: Path, chat_format: str) -> str | None:
    parsed = urlparse(chat_format)
    if parsed.scheme in {"http", "https"}:
        with urlopen(chat_format) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset)

    if chat_format.lower().endswith(".jinja") or Path(chat_format).suffix == ".jinja":
        template_path = resolve_config_path(config_dir, chat_format, chat_format)
        if not template_path.exists():
            raise RuntimeError(f"chat_format template not found: {template_path}")
        return template_path.read_text()

    return None


def load_chat_template(chat_format: str) -> str | None:
    config_path = _config_path()
    return _load_chat_template(config_path.parent, chat_format)


@lru_cache(maxsize=1)
def load_settings() -> LlamaCppSettings:
    config_path = _config_path()
    config = load_yaml_config(config_path)
    model_dir = resolve_config_path(config_path.parent, config.get("model_dir"), "models")
    chat_format = str(config.get("chat_format", "chatml-function-calling")).strip()
    model_id = str(config.get("model_id", "")).strip()
    if not model_id:
        raise RuntimeError("model_id is not set.")
    quantization = str(config.get("quantization", "")).strip()
    if not quantization:
        raise RuntimeError("quantization is not set.")

    return LlamaCppSettings(
        host=str(config.get("host", "127.0.0.1")).strip(),
        port=int(config.get("port", 9100)),
        reload=bool(config.get("reload", True)),
        log_level=str(config.get("log_level", "info")).lower().strip(),
        chat_format=chat_format,
        model_id=model_id,
        quantization=quantization,
        model_dir=model_dir,
        n_ctx=int(config.get("n_ctx", 4096)),
        n_gpu_layers=int(config.get("n_gpu_layers", 0)),
        n_threads=int(config.get("n_threads", 0)),
        temperature=float(config.get("temperature", 0.2)),
        n_batch=int(config.get("n_batch", 512)),
        seed=int(config.get("seed", 42)),
    )
