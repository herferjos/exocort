import base64
import inspect
import json
import logging
from pathlib import Path

from llama_cpp import Llama

from ai.steps import StepConfig, StepOutputConfig, extract_json_path, format_step_outputs, render_prompt
from .base import OcrEngine

log = logging.getLogger("ai.ocr.llama_cpp")

_model = None
_model_key = None


def _config_key(cfg: dict) -> str:
    parts = [
        str(cfg.get("model_path", "")),
        str(cfg.get("context_length", "")),
        str(cfg.get("n_gpu_layers", "")),
        str(cfg.get("threads", "")),
        str(cfg.get("batch_size", "")),
        str(cfg.get("use_mmap", "")),
        str(cfg.get("flash_attention", "")),
        str(cfg.get("offload_kqv", "")),
        str(cfg.get("seed", "")),
        str(cfg.get("chat_format", "")),
        str(cfg.get("clip_model_path", "")),
        str(cfg.get("chat_template", "")),
    ]
    return "|".join(parts)


def _get_model(cfg: dict):
    global _model, _model_key
    key = _config_key(cfg)
    if _model is not None and _model_key == key:
        return _model

    model_path = cfg.get("model_path")
    if not model_path:
        raise FileNotFoundError("OCR llama_cpp requires 'model_path' in ocr.json")

    kwargs = {
        "model_path": model_path,
        "n_ctx": cfg.get("context_length", 4096),
        "n_threads": cfg.get("threads", 4),
        "n_gpu_layers": cfg.get("n_gpu_layers", -1),
        "n_batch": cfg.get("batch_size", 512),
        "use_mmap": cfg.get("use_mmap", True),
        "verbose": False,
    }
    if cfg.get("seed") is not None:
        kwargs["seed"] = cfg.get("seed")
    if cfg.get("flash_attention") is not None and hasattr(Llama, "flash_attn"):
        kwargs["flash_attn"] = cfg.get("flash_attention")
    if cfg.get("offload_kqv") is not None and hasattr(Llama, "offload_kqv"):
        kwargs["offload_kqv"] = cfg.get("offload_kqv")
    sig = inspect.signature(Llama.__init__)
    if cfg.get("chat_format") and "chat_format" in sig.parameters:
        kwargs["chat_format"] = cfg.get("chat_format")
    if cfg.get("chat_template") and "chat_template" in sig.parameters:
        kwargs["chat_template"] = cfg.get("chat_template")
    if cfg.get("clip_model_path") and "clip_model_path" in sig.parameters:
        kwargs["clip_model_path"] = cfg.get("clip_model_path")

    if cfg.get("chat_template") and "chat_template" not in sig.parameters:
        raise ValueError(
            "llama_cpp does not support 'chat_template' in this version. "
            "Upgrade llama-cpp-python or set a supported chat_format."
        )
    if cfg.get("clip_model_path") and "clip_model_path" not in sig.parameters:
        raise ValueError(
            "llama_cpp does not support 'clip_model_path' in this version. "
            "Upgrade llama-cpp-python for vision support."
        )

    _model = Llama(**kwargs)
    _model_key = key
    return _model


class LlamaCppOcrEngine(OcrEngine):
    def __init__(
        self,
        model_path: str,
        context_length: int,
        n_gpu_layers: int,
        threads: int,
        batch_size: int,
        flash_attention: bool,
        use_mmap: bool,
        offload_kqv: bool,
        seed: int | None,
        chat_format: str | None,
        chat_template: str | None,
        clip_model_path: str | None,
        steps: list[StepConfig] | None = None,
        output: StepOutputConfig | None = None,
    ):
        self._cfg = {
            "model_path": model_path,
            "context_length": context_length,
            "n_gpu_layers": n_gpu_layers,
            "threads": threads,
            "batch_size": batch_size,
            "flash_attention": flash_attention,
            "use_mmap": use_mmap,
            "offload_kqv": offload_kqv,
            "seed": seed,
            "chat_format": chat_format,
            "chat_template": chat_template,
            "clip_model_path": clip_model_path,
        }
        self.steps = steps or []
        self.output = output

    def _parse_step_output(self, step: StepConfig, text: str) -> str:
        raw = text.strip()
        if step.response_type.lower() != "json":
            return raw
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return raw
        extracted = extract_json_path(payload, step.response_path)
        if extracted is None:
            return raw
        if isinstance(extracted, str):
            return extracted.strip()
        return json.dumps(extracted, ensure_ascii=False)

    def _run_step(
        self,
        model: Llama,
        step: StepConfig,
        messages: list[dict],
        image_b64: str | None,
        context: dict[str, str],
        include_image: bool,
    ) -> str:
        system_prompt = render_prompt(step.system_prompt, context).strip()
        user_prompt = render_prompt(step.user_prompt, context).strip()

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        content_parts = []
        if user_prompt:
            content_parts.append({"type": "text", "text": user_prompt})
        if include_image and image_b64:
            content_parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                }
            )
        if not content_parts:
            content_parts.append({"type": "text", "text": "Extract text from the image."})
        if len(content_parts) == 1 and content_parts[0].get("type") == "text":
            messages.append({"role": "user", "content": content_parts[0].get("text", "")})
        else:
            messages.append({"role": "user", "content": content_parts})

        req: dict = {"messages": messages}
        if step.temperature is not None:
            req["temperature"] = step.temperature
        if step.max_tokens is not None:
            req["max_tokens"] = step.max_tokens

        out = model.create_chat_completion(**req)
        choice = (out.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content", "")
        return self._parse_step_output(step, str(content))

    def extract_text(self, path: Path) -> str:
        try:
            model = _get_model(self._cfg)
            image_b64 = base64.b64encode(path.read_bytes()).decode("utf-8")

            if not self.steps:
                step = StepConfig(
                    step_id="ocr",
                    system_prompt=None,
                    user_prompt="Extract all readable text from the image. Return plain text only.",
                    response_type="text",
                    response_path=None,
                    temperature=None,
                    max_tokens=None,
                )
                result = self._run_step(model, step, [], image_b64, {}, include_image=True)
                return result.strip()

            results: list[tuple[str, str]] = []
            context: dict[str, str] = {}
            messages: list[dict] = []
            for idx, step in enumerate(self.steps):
                include_image = idx == 0
                text = self._run_step(model, step, messages, image_b64, context, include_image=include_image)
                results.append((step.step_id, text))
                context["prev"] = text
                context[step.step_id] = text
                messages.append({"role": "assistant", "content": text})
            return format_step_outputs(results, self.output)
        except Exception as exc:
            log.warning("llama_cpp OCR failed | path=%s | error=%s", path, exc)
            return ""
