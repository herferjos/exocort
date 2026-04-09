from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

from fastapi import HTTPException
from huggingface_hub import hf_hub_download
from llama_cpp import Llama

from .models import ChatCompletionRequest, ChatMessage
from ..config import LlamaCppSettings, load_settings


log = logging.getLogger("llama_cpp")

_settings: LlamaCppSettings | None = None
_llama = None
_llama_lock = threading.Lock()


def _model_name(settings: LlamaCppSettings) -> str:
    return settings.model_id


def _ensure_model_path(settings: LlamaCppSettings):
    model_name = settings.model_id.split("/")[-1].replace("-GGUF", "")
    filename = f"{model_name}-{settings.quantization}.gguf"
    local_path = settings.model_dir / filename
    if local_path.exists():
        return local_path

    settings.model_dir.mkdir(parents=True, exist_ok=True)
    hf_hub_download(
        repo_id=settings.model_id,
        filename=filename,
        local_dir=str(settings.model_dir),
        local_dir_use_symlinks=False,
    )
    return local_path


def _load_llama(settings: LlamaCppSettings):
    model_path = _ensure_model_path(settings)
    kwargs: dict[str, Any] = {
        "model_path": str(model_path),
        "n_ctx": settings.n_ctx,
        "n_gpu_layers": settings.n_gpu_layers,
        "n_batch": settings.n_batch,
        "seed": settings.seed,
    }
    if settings.n_threads > 0:
        kwargs["n_threads"] = settings.n_threads
    return Llama(**kwargs)


def _normalize_messages(messages: list[ChatMessage]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for msg in messages:
        content = msg.content
        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        text_parts.append(text)
            content_str = "\n".join(text_parts).strip()
        else:
            content_str = (content or "").strip()
        out.append({"role": msg.role, "content": content_str})
    return out


def startup() -> None:
    global _settings, _llama
    _settings = load_settings()
    try:
        _llama = _load_llama(_settings)
    except Exception:
        log.exception("Failed to load llama model")
        raise


def health() -> dict[str, object]:
    return {"ok": _llama is not None}


def list_models() -> dict[str, Any]:
    settings = _settings or load_settings()
    model_name = _model_name(settings)
    return {
        "object": "list",
        "data": [
            {
                "id": model_name,
                "object": "model",
                "owned_by": "local",
            }
        ],
    }


def chat_completions(payload: ChatCompletionRequest) -> dict[str, Any]:
    if payload.stream:
        raise HTTPException(status_code=400, detail="streaming is not supported")
    if _llama is None:
        raise HTTPException(status_code=503, detail="model not loaded")

    settings = _settings or load_settings()
    model_name = _model_name(settings)
    messages = _normalize_messages(payload.messages)
    temperature = payload.temperature if payload.temperature is not None else settings.temperature

    try:
        kwargs: dict[str, Any] = {
            "messages": messages,
            "temperature": temperature,
        }
        if payload.max_tokens is not None:
            kwargs["max_tokens"] = payload.max_tokens
        if payload.top_p is not None:
            kwargs["top_p"] = payload.top_p
        if payload.stop is not None:
            kwargs["stop"] = payload.stop
        if payload.response_format is not None:
            kwargs["response_format"] = payload.response_format
        with _llama_lock:
            response = _llama.create_chat_completion(**kwargs)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not isinstance(response, dict):
        try:
            response = json.loads(response)
        except Exception:
            raise HTTPException(status_code=500, detail="invalid model response")

    response.setdefault("id", f"chatcmpl-{int(time.time() * 1000)}")
    response.setdefault("object", "chat.completion")
    response.setdefault("created", int(time.time()))
    response.setdefault("model", payload.model or model_name)
    response.setdefault("choices", [])
    response.setdefault(
        "usage",
        {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    )
    return response


__all__ = [
    "ChatCompletionRequest",
    "ChatMessage",
    "chat_completions",
    "health",
    "list_models",
    "startup",
]
