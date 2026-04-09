from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LlamaCppSettings:
    host: str
    port: int
    model_id: str
    quantization: str
    model_dir: Path
    n_ctx: int
    n_gpu_layers: int
    n_threads: int
    temperature: float
    n_batch: int
    seed: int
