from __future__ import annotations

from dataclasses import dataclass

import settings
from ai.config import load_json_config, read_bool, read_float, read_int, read_str


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str | None
    base_url: str | None
    api_key: str | None
    api_key_env: str | None
    model_path: str | None
    context_length: int
    n_gpu_layers: int
    threads: int
    batch_size: int
    flash_attention: bool
    use_mmap: bool
    offload_kqv: bool
    seed: int | None
    max_tokens: int
    temperature: float
    max_retries: int
    concurrency: int
    processor_prompts: dict[str, dict[str, str]]


_llm_config: LLMConfig | None = None


def _load_config() -> LLMConfig:
    path = settings.llm_config_path()
    data = load_json_config(path, "LLM")

    provider = (read_str(data, "provider", "llama_cpp") or "llama_cpp").lower()
    model = read_str(data, "model", None)
    base_url = read_str(data, "base_url", None)
    api_key = read_str(data, "api_key", None)
    api_key_env = read_str(data, "api_key_env", None)

    model_path = read_str(data, "model_path", None)
    if model_path is None and "modelPath" in data:
        model_path = read_str(data, "modelPath", None)

    context_length = read_int(data, "context_length", 4096)
    n_gpu_layers = read_int(data, "n_gpu_layers", -1)
    threads = read_int(data, "threads", 4)
    batch_size = read_int(data, "batch_size", 512)
    flash_attention = read_bool(data, "flash_attention", False)
    use_mmap = read_bool(data, "use_mmap", True)
    offload_kqv = read_bool(data, "offload_kqv", False)

    seed_value = data.get("seed")
    seed = None
    if seed_value is not None and seed_value != "":
        try:
            seed = int(seed_value)
        except (TypeError, ValueError):
            seed = None

    max_tokens = read_int(data, "max_tokens", 4096)
    temperature = read_float(data, "temperature", 0.3)

    max_retries = read_int(data, "max_retries", 3)
    if max_retries < 1:
        max_retries = 1

    concurrency = read_int(data, "concurrency", 1)
    if concurrency < 1:
        concurrency = 1

    prompts_raw = data.get("processor_prompts") if isinstance(data.get("processor_prompts"), dict) else None
    if prompts_raw is None and isinstance(data.get("prompts"), dict):
        prompts_raw = data.get("prompts")
    processor_prompts: dict[str, dict[str, str]] = {}
    if isinstance(prompts_raw, dict):
        for key, value in prompts_raw.items():
            if not isinstance(value, dict):
                continue
            processor_prompts[key] = {
                str(field): str(text)
                for field, text in value.items()
                if isinstance(text, (str, int, float))
            }

    return LLMConfig(
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
        api_key_env=api_key_env,
        model_path=model_path,
        context_length=context_length,
        n_gpu_layers=n_gpu_layers,
        threads=threads,
        batch_size=batch_size,
        flash_attention=flash_attention,
        use_mmap=use_mmap,
        offload_kqv=offload_kqv,
        seed=seed,
        max_tokens=max_tokens,
        temperature=temperature,
        max_retries=max_retries,
        concurrency=concurrency,
        processor_prompts=processor_prompts,
    )


def get_llm_config() -> LLMConfig:
    global _llm_config
    if _llm_config is None:
        _llm_config = _load_config()
    return _llm_config


def get_processor_prompt(section: str, field: str) -> str:
    cfg = get_llm_config()
    raw = cfg.processor_prompts.get(section, {})
    value = raw.get(field) if isinstance(raw, dict) else None
    if isinstance(value, str) and value.strip():
        return value
    if isinstance(value, (int, float)):
        return str(value)
    raise ValueError(
        f"Missing processor prompt '{section}.{field}' in LLM config. "
        "Define it under 'processor_prompts' in llm.json."
    )
