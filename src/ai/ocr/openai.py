import base64
import json
import logging
from pathlib import Path

from openai import OpenAI

from ai.config import resolve_api_key
from ai.steps import StepConfig, StepOutputConfig, extract_json_path, format_step_outputs, render_prompt
from .base import OcrEngine

log = logging.getLogger("ai.ocr.openai")


class OpenAIOcrEngine(OcrEngine):
    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        api_key_env: str | None = None,
        base_url: str | None = None,
        steps: list[StepConfig] | None = None,
        output: StepOutputConfig | None = None,
    ):
        api_key = resolve_api_key(api_key, api_key_env, "OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI OCR")
        self.client = OpenAI(api_key=api_key, base_url=(base_url or "https://api.openai.com/v1").rstrip("/"))
        self.model = model
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

    def _run_step(self, step: StepConfig, b64: str, context: dict[str, str]) -> str:
        system_prompt = render_prompt(step.system_prompt, context).strip()
        user_prompt = render_prompt(step.user_prompt, context).strip()
        if not system_prompt and not user_prompt:
            user_prompt = "Extract all readable text from the image. Return plain text only."

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        user_content = []
        if user_prompt:
            user_content.append({"type": "input_text", "text": user_prompt})
        user_content.append({"type": "input_image", "image_url": f"data:image/png;base64,{b64}"})
        messages.append({"role": "user", "content": user_content})

        req = {"model": self.model, "input": messages}
        if step.temperature is not None:
            req["temperature"] = step.temperature
        if step.max_tokens is not None:
            req["max_output_tokens"] = step.max_tokens
        resp = self.client.responses.create(**req)
        text = (getattr(resp, "output_text", None) or "").strip()
        return self._parse_step_output(step, text)

    def extract_text(self, path: Path) -> str:
        try:
            b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
            if not self.steps:
                prompt = "Extract all readable text from the image. Return plain text only."
                resp = self.client.responses.create(
                    model=self.model,
                    input=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "input_text", "text": prompt},
                                {
                                    "type": "input_image",
                                    "image_url": f"data:image/png;base64,{b64}",
                                },
                            ],
                        }
                    ],
                )
                return (getattr(resp, "output_text", None) or "").strip()

            results: list[tuple[str, str]] = []
            context: dict[str, str] = {}
            for step in self.steps:
                text = self._run_step(step, b64, context)
                results.append((step.step_id, text))
                context["prev"] = text
                context[step.step_id] = text
            return format_step_outputs(results, self.output)
        except Exception as exc:
            log.warning("OpenAI OCR failed | path=%s | error=%s", path, exc)
            return ""
