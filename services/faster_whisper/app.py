from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, UploadFile

from .config import FasterWhisperSettings, load_settings


def _create_model(settings: FasterWhisperSettings):
    from faster_whisper import WhisperModel

    return WhisperModel(
        settings.model_path,
        device=settings.device,
        compute_type=settings.compute_type,
    )


settings = load_settings()
model = None

app = FastAPI(title="Faster Whisper", version="0.1.0")


def get_model():
    global model
    if model is None:
        model = _create_model(settings)
    return model


@app.post("/v1/audio/transcriptions")
async def transcribe_audio(
    file: UploadFile = File(...),
    model_name: Annotated[str | None, Form()] = None,
    language: Annotated[str | None, Form()] = None,
    prompt: Annotated[str | None, Form()] = None,
) -> dict[str, str]:
    tmp_path = Path(f"/tmp/{file.filename}")
    try:
        content = await file.read()
        tmp_path.write_bytes(content)

        segments, info = get_model().transcribe(
            str(tmp_path),
            beam_size=settings.beam_size,
            language=language or settings.language,
            vad_filter=settings.vad_filter,
            initial_prompt=prompt or None,
        )

        text_parts: list[str] = [segment.text.strip() for segment in segments if segment.text]
        text = " ".join(text_parts).strip()
        return {"text": text}
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            # Best-effort cleanup; ignore errors
            pass


def main() -> None:
    import uvicorn

    uvicorn.run("services.faster_whisper.app:app", host="127.0.0.1", port=9000, reload=False)


__all__ = ["app", "get_model", "main"]
