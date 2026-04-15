from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from fastapi import HTTPException
from huggingface_hub import hf_hub_download
from llama_cpp import Llama

from common.models.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ChatModel,
    ChatModelListResponse,
)
from common.models.health import HealthResponse
from common.utils.logs import get_logger

from ..config.models import LlamaCppSettings
from ..config.settings import load_settings

log = get_logger("llama_cpp", "chat")
_settings: LlamaCppSettings | None = None
_llama: Llama | None = None
_llama_lock = threading.Lock()


def _model_name(settings: LlamaCppSettings) -> str:
    return settings.model_id


def _ensure_model_path(settings: LlamaCppSettings) -> Path:
    model_name = settings.model_id.split("/")[-1].replace("-GGUF", "")
    filename = f"{model_name}-{settings.quantization}.gguf"
    local_path = settings.model_dir / filename
    if local_path.exists():
        return local_path
    log.info(
        "Downloading llama.cpp model | model_id=%s | filename=%s | model_dir=%s",
        settings.model_id,
        filename,
        settings.model_dir,
    )
    settings.model_dir.mkdir(parents=True, exist_ok=True)
    hf_hub_download(
        repo_id=settings.model_id,
        filename=filename,
        local_dir=str(settings.model_dir),
        local_dir_use_symlinks=False,
    )
    log.info("Downloaded llama.cpp model | path=%s", local_path)
    return local_path


def _load_llama(settings: LlamaCppSettings) -> Llama:
    model_path = _ensure_model_path(settings)
    kwargs: dict[str, object] = {
        "model_path": str(model_path),
        "chat_format": settings.chat_format,
        "n_ctx": settings.n_ctx,
        "n_gpu_layers": settings.n_gpu_layers,
        "n_batch": settings.n_batch,
        "seed": settings.seed,
        "verbose": False,
    }
    if settings.n_threads > 0:
        kwargs["n_threads"] = settings.n_threads
    return Llama(**kwargs)


def _normalize_messages(messages: list[ChatMessage]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for msg in messages:
        content = msg.content
        if isinstance(content, list):
            text_parts = [
                item.text.strip()
                for item in content
                if item.text is not None and item.text.strip()
            ]
            content_str = "\n".join(text_parts).strip()
        else:
            content_str = (content or "").strip()
        normalized: dict[str, object] = {"role": msg.role, "content": content_str}
        if msg.name is not None:
            normalized["name"] = msg.name
        if msg.tool_call_id is not None:
            normalized["tool_call_id"] = msg.tool_call_id
        if msg.tool_calls is not None:
            normalized["tool_calls"] = msg.tool_calls
        out.append(normalized)
    return out


def startup() -> None:
    global _settings, _llama
    _settings = load_settings()
    log.info(
        "Starting llama.cpp service | model_id=%s | model_dir=%s | chat_format=%s",
        _settings.model_id,
        _settings.model_dir,
        _settings.chat_format,
    )
    try:
        _llama = _load_llama(_settings)
        log.info(
            "Loaded llama.cpp model | path=%s | model_id=%s | quantization=%s | n_ctx=%s | n_gpu_layers=%s | n_threads=%s | n_batch=%s",
            _ensure_model_path(_settings),
            _settings.model_id,
            _settings.quantization,
            _settings.n_ctx,
            _settings.n_gpu_layers,
            _settings.n_threads,
            _settings.n_batch,
        )
    except Exception:
        log.exception(
            "Failed to load llama.cpp model | model_id=%s | model_dir=%s",
            _settings.model_id,
            _settings.model_dir,
        )
        raise


def health() -> HealthResponse:
    return HealthResponse(ok=_llama is not None)


def list_models() -> ChatModelListResponse:
    settings = _settings or load_settings()
    return ChatModelListResponse(data=[ChatModel(id=_model_name(settings), owned_by="local")])


def chat_completions(payload: ChatCompletionRequest) -> ChatCompletionResponse:
    if payload.stream:
        raise HTTPException(status_code=400, detail="streaming is not supported")
    if _llama is None:
        raise HTTPException(status_code=503, detail="model not loaded")
    settings = _settings or load_settings()
    model_name = _model_name(settings)
    messages = _normalize_messages(payload.messages)
    temperature = payload.temperature if payload.temperature is not None else settings.temperature
    log.debug(
        "Creating chat completion | model=%s | messages=%s | temperature=%s | max_tokens=%s | top_p=%s | tools=%s | tool_choice=%s",
        payload.model or model_name,
        len(messages),
        temperature,
        payload.max_tokens,
        payload.top_p,
        payload.tools is not None,
        payload.tool_choice is not None,
    )
    log.debug(
        "Chat completion input | model=%s | messages=%s",
        payload.model or model_name,
        json.dumps(messages, ensure_ascii=False, default=str),
    )
    try:
        kwargs: dict[str, object] = {"messages": messages, "temperature": temperature}
        if payload.max_tokens is not None:
            kwargs["max_tokens"] = payload.max_tokens
        if payload.top_p is not None:
            kwargs["top_p"] = payload.top_p
        if payload.stop is not None:
            kwargs["stop"] = payload.stop
        if payload.response_format is not None:
            kwargs["response_format"] = payload.response_format
        if payload.tools is not None:
            kwargs["tools"] = payload.tools
        if payload.tool_choice is not None:
            kwargs["tool_choice"] = payload.tool_choice
        with _llama_lock:
            response: object = _llama.create_chat_completion(**kwargs)
    except Exception as exc:
        log.exception("Failed to create chat completion | model=%s", payload.model or model_name)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if isinstance(response, dict):
        response_data: dict[str, object] = response
    else:
        try:
            if not isinstance(response, (str, bytes, bytearray)):
                raise TypeError("invalid model response")
            loaded_response = json.loads(response)
        except Exception:
            log.error("Invalid llama.cpp model response | model=%s", payload.model or model_name)
            raise HTTPException(status_code=500, detail="invalid model response")
        if not isinstance(loaded_response, dict):
            log.error("Invalid llama.cpp model response type | model=%s", payload.model or model_name)
            raise HTTPException(status_code=500, detail="invalid model response")
        response_data = loaded_response
    response_data.setdefault("id", f"chatcmpl-{int(time.time() * 1000)}")
    response_data.setdefault("object", "chat.completion")
    response_data.setdefault("created", int(time.time()))
    response_data.setdefault("model", payload.model or model_name)
    response_data.setdefault("choices", [])
    response_data.setdefault(
        "usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    )
    log.debug(
        "Chat completion output | model=%s | response=%s",
        response_data.get("model"),
        json.dumps(response_data, ensure_ascii=False, default=str),
    )
    log.debug(
        "Finished chat completion | model=%s | choices=%s",
        response_data.get("model"),
        len(response_data.get("choices", []))
        if isinstance(response_data.get("choices", []), list)
        else "unknown",
    )
    return ChatCompletionResponse.model_validate(response_data)
