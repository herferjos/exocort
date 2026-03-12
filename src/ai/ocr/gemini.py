import json
import logging
from pathlib import Path

from google import genai
from google.genai import types

from ai.config import resolve_api_key
from ai.steps import StepConfig, StepOutputConfig, extract_json_path, format_step_outputs, render_prompt
from .base import OcrEngine

log = logging.getLogger("ai.ocr.gemini")


class GeminiOcrEngine(OcrEngine):
    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        api_key_env: str | None = None,
        steps: list[StepConfig] | None = None,
        output: StepOutputConfig | None = None,
    ):
        api_key = resolve_api_key(api_key, api_key_env, "GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required for Gemini OCR")
        self._types = types
        self.client = genai.Client(api_key=api_key)
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

    def _run_step(self, step: StepConfig, part, context: dict[str, str]) -> str:
        system_prompt = render_prompt(step.system_prompt, context).strip()
        user_prompt = render_prompt(step.user_prompt, context).strip()
        if not system_prompt and not user_prompt:
            user_prompt = "Extract all readable text from the image. Return plain text only."

        contents = [part] if not user_prompt else [user_prompt, part]
        config = {"system_instruction": system_prompt} if system_prompt else {}
        if step.temperature is not None:
            config["temperature"] = step.temperature
        if step.max_tokens is not None:
            config["max_output_tokens"] = step.max_tokens
        if not config:
            config = None
        resp = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )
        text = (getattr(resp, "text", None) or "").strip()
        return self._parse_step_output(step, text)

    def extract_text(self, path: Path) -> str:
        try:
            img_bytes = path.read_bytes()
            part = self._types.Part.from_bytes(
                data=img_bytes,
                mime_type="image/png",
            )

            if not self.steps:
                prompt = "Extract all readable text from the image. Return plain text only."
                resp = self.client.models.generate_content(
                    model=self.model,
                    contents=[prompt, part],
                )
                return (getattr(resp, "text", None) or "").strip()

            results: list[tuple[str, str]] = []
            context: dict[str, str] = {}
            for step in self.steps:
                text = self._run_step(step, part, context)
                results.append((step.step_id, text))
                context["prev"] = text
                context[step.step_id] = text
            return format_step_outputs(results, self.output)
        except Exception as exc:
            log.warning("Gemini OCR failed | path=%s | error=%s", path, exc)
            return ""
