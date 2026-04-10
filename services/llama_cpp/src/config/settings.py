from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from common import EnvReader

from .models import LlamaCppSettings


@lru_cache(maxsize=1)
def load_settings() -> LlamaCppSettings:
    env = EnvReader()
    model_dir_raw = env.str("LLAMA_CPP_MODEL_DIR", "")
    model_dir = Path(model_dir_raw).expanduser().resolve() if model_dir_raw else Path.cwd() / "models"
    model_id = env.str("LLAMA_CPP_MODEL_ID", "")
    if not model_id:
        raise RuntimeError("LLAMA_CPP_MODEL_ID is not set.")
    quantization = env.str("LLAMA_CPP_QUANTIZATION", "")
    if not quantization:
        raise RuntimeError("LLAMA_CPP_QUANTIZATION is not set.")

    return LlamaCppSettings(
        host=env.str("LLAMA_CPP_HOST", "127.0.0.1"),
        port=env.int("LLAMA_CPP_PORT", 9100),
        reload=env.bool("LLAMA_CPP_RELOAD", True),
        log_level=env.str("LLAMA_CPP_LOG_LEVEL", "info").lower(),
        model_id=model_id,
        quantization=quantization,
        model_dir=model_dir,
        n_ctx=env.int("LLAMA_CPP_CTX", 4096),
        n_gpu_layers=env.int("LLAMA_CPP_N_GPU_LAYERS", 0),
        n_threads=env.int("LLAMA_CPP_THREADS", 0),
        temperature=env.float("LLAMA_CPP_TEMPERATURE", 0.2),
        n_batch=env.int("LLAMA_CPP_N_BATCH", 512),
        seed=env.int("LLAMA_CPP_SEED", 42),
    )
