from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from .models import LlamaCppSettings


def _str(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _int(key: str, default: int) -> int:
    raw = _str(key, str(default))
    try:
        return int(raw)
    except ValueError:
        return default


def _float(key: str, default: float) -> float:
    raw = _str(key, str(default))
    try:
        return float(raw)
    except ValueError:
        return default


def load_settings() -> LlamaCppSettings:
    load_dotenv()
    model_dir_raw = _str("LLAMA_CPP_MODEL_DIR", "")
    model_dir = (
        Path(model_dir_raw).expanduser().resolve()
        if model_dir_raw
        else Path.cwd() / "models"
    )
    model_id = _str("LLAMA_CPP_MODEL_ID", "")
    if not model_id:
        raise RuntimeError("LLAMA_CPP_MODEL_ID is not set.")
    quantization = _str("LLAMA_CPP_QUANTIZATION", "")
    if not quantization:
        raise RuntimeError("LLAMA_CPP_QUANTIZATION is not set.")

    return LlamaCppSettings(
        host=_str("LLAMA_CPP_HOST", "127.0.0.1"),
        port=_int("LLAMA_CPP_PORT", 9100),
        model_id=model_id,
        quantization=quantization,
        model_dir=model_dir,
        n_ctx=_int("LLAMA_CPP_CTX", 4096),
        n_gpu_layers=_int("LLAMA_CPP_N_GPU_LAYERS", 0),
        n_threads=_int("LLAMA_CPP_THREADS", 0),
        temperature=_float("LLAMA_CPP_TEMPERATURE", 0.2),
        n_batch=_int("LLAMA_CPP_N_BATCH", 512),
        seed=_int("LLAMA_CPP_SEED", 42),
    )


__all__ = ["LlamaCppSettings", "load_settings"]
