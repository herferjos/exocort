"""Local GGUF model via llama-cpp-python (in-process)."""
import logging
import os
import threading
from typing import Type

from pydantic import BaseModel

from . import base
from .config import LLMConfig
from llama_cpp import Llama, LlamaGrammar
from llama_cpp_agent.gbnf_grammar_generator.gbnf_grammar_from_pydantic_models import (
    generate_gbnf_grammar_and_documentation,
)

log = logging.getLogger("processor.llm.llama_cpp")

_model = None
_model_key = None
_model_lock = threading.Lock()


def _grammar_and_docs_from_pydantic(model: Type[BaseModel]) -> tuple[LlamaGrammar, str]:
    """Build LlamaGrammar and documentation from a Pydantic model using GBNF."""
    gbnf_grammar, documentation = generate_gbnf_grammar_and_documentation([model])
    grammar = LlamaGrammar.from_string(gbnf_grammar, verbose=False)
    return grammar, documentation


def _config_key(cfg: LLMConfig) -> str:
    return "|".join(
        [
            str(cfg.model_path or ""),
            str(cfg.context_length),
            str(cfg.n_gpu_layers),
            str(cfg.threads),
            str(cfg.batch_size),
            str(cfg.use_mmap),
            str(cfg.flash_attention),
            str(cfg.offload_kqv),
            str(cfg.seed),
        ]
    )


def _get_model(cfg: LLMConfig):
    global _model, _model_key
    key = _config_key(cfg)
    if _model is not None and _model_key == key:
        return _model
    with _model_lock:
        if _model is not None and _model_key == key:
            return _model

        model_path = cfg.model_path or ""
        if not model_path or not os.path.exists(model_path):
            raise FileNotFoundError(
                f"LLM model file not found: {model_path}. Set 'model_path' in your llm.json."
            )

        log.info(
            "Loading local GGUF model | path=%s | ctx=%d | gpu_layers=%d | threads=%d | batch=%d",
            model_path,
            cfg.context_length,
            cfg.n_gpu_layers,
            cfg.threads,
            cfg.batch_size,
        )

        llama_kwargs = {
            "model_path": model_path,
            "n_ctx": cfg.context_length,
            "n_threads": cfg.threads,
            "n_gpu_layers": cfg.n_gpu_layers,
            "n_batch": cfg.batch_size,
            "use_mmap": cfg.use_mmap,
            "verbose": False,
        }
        if cfg.seed is not None:
            llama_kwargs["seed"] = cfg.seed

        if hasattr(Llama, "flash_attn"):
            llama_kwargs["flash_attn"] = cfg.flash_attention
        if hasattr(Llama, "offload_kqv"):
            llama_kwargs["offload_kqv"] = cfg.offload_kqv

        _model = Llama(**llama_kwargs)
        _model_key = key
        log.info("Local GGUF model loaded")
        return _model


class LocalLlamaClient(base.LLMClient):
    """Client using llama-cpp-python with a local .gguf file."""

    def __init__(self, cfg: LLMConfig):
        self._cfg = cfg

    def generate(self, system: str, user: str, output_model: Type[base.T]) -> base.T:
        model = _get_model(self._cfg)
        log.info("Using local GGUF model for structured generation")

        grammar, documentation = _grammar_and_docs_from_pydantic(output_model)
        system_with_docs = f"{system}\n\n{documentation}"
        messages = [
            {"role": "system", "content": system_with_docs},
            {"role": "user", "content": user},
        ]

        out = model.create_chat_completion(
            messages=messages,
            temperature=self._cfg.temperature,
            max_tokens=self._cfg.max_tokens,
            grammar=grammar,
        )
        choice = (out.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content", "")

        try:
            return output_model.model_validate_json(content)
        except Exception as e:
            log.error("Failed to validate structured output from local model: %s", e)
            log.error("Raw model output: %s", content)
            raise
