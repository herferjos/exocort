from __future__ import annotations

from pathlib import Path

from faster_whisper import WhisperModel

from src.config import load_settings


settings = load_settings()

model = WhisperModel(
    settings.model_path,
    device=settings.device,
    compute_type=settings.compute_type,
)


def transcribe_path(
    path: Path,
    *,
    language: str | None,
    prompt: str | None,
) -> dict[str, object] | None:
    segments, _info = model.transcribe(
        str(path),
        beam_size=settings.beam_size,
        language=language or settings.language,
        initial_prompt=prompt or None,
    )

    text_parts: list[str] = [segment.text.strip() for segment in segments if segment.text]
    text = " ".join(text_parts).strip()
    if not text:
        return None
    return {
        "text": text,
        "task": "transcribe",
        "language": language or settings.language,
        "duration": None,
    }


__all__ = ["settings", "transcribe_path"]
