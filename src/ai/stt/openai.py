import json
import logging
from pathlib import Path

from openai import OpenAI

from ai.config import resolve_api_key
from ai.steps import StepConfig, StepOutputConfig, extract_json_path, format_step_outputs, render_prompt
from .base import SpeechTranscriber

log = logging.getLogger("ai.stt.openai")


class OpenAITranscriber(SpeechTranscriber):
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
            raise ValueError("OPENAI_API_KEY is required for OpenAI STT")
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

    def _run_step(self, step: StepConfig, path: Path, context: dict[str, str]) -> str:
        system_prompt = render_prompt(step.system_prompt, context).strip()
        user_prompt = render_prompt(step.user_prompt, context).strip()
        prompt_parts = [part for part in [system_prompt, user_prompt] if part]
        prompt = "\n".join(prompt_parts).strip()
        with path.open("rb") as f:
            resp = self.client.audio.transcriptions.create(
                model=self.model,
                file=f,
                prompt=prompt or None,
            )
        text = (getattr(resp, "text", None) or "").strip()
        return self._parse_step_output(step, text)

    def transcribe(self, path: Path, mime_type: str | None = None) -> str:
        try:
            if not self.steps:
                with path.open("rb") as f:
                    resp = self.client.audio.transcriptions.create(
                        model=self.model,
                        file=f,
                    )
                return (getattr(resp, "text", None) or "").strip()

            results: list[tuple[str, str]] = []
            context: dict[str, str] = {}
            for step in self.steps:
                text = self._run_step(step, path, context)
                results.append((step.step_id, text))
                context["prev"] = text
                context[step.step_id] = text
            return format_step_outputs(results, self.output)
        except Exception as exc:
            log.warning("OpenAI transcription failed | path=%s | error=%s", path, exc)
            return ""
