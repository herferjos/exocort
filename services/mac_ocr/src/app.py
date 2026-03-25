from __future__ import annotations

import base64
import binascii
import time
from pathlib import Path
from tempfile import gettempdir
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from .config import HOST, PORT
from .ocr import ocr_image_path


app = FastAPI(title="Mac OCR", version="0.1.0")


class InputTextContent(BaseModel):
    type: Literal["text"]
    text: str


class InputImageUrl(BaseModel):
    url: str


class InputImageContent(BaseModel):
    type: Literal["image_url"]
    image_url: InputImageUrl


class ChatMessage(BaseModel):
    role: str
    content: str | list[InputTextContent | InputImageContent] | None = None


class ChatCompletionRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage]
    stream: bool | None = False


@app.get("/health")
def health() -> dict[str, object]:
    return {"ok": True}


def _decode_data_url(url: str) -> tuple[bytes, str]:
    prefix = "data:"
    if not url.startswith(prefix):
        raise HTTPException(status_code=400, detail="Only data URLs are supported.")

    header, _, encoded = url.partition(",")
    if not encoded or ";base64" not in header:
        raise HTTPException(status_code=400, detail="Invalid image data URL.")

    media_type = header[len(prefix) :].split(";", 1)[0].strip() or "image/jpeg"
    suffix = ".png" if media_type == "image/png" else ".jpg"
    try:
        return base64.b64decode(encoded, validate=True), suffix
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(status_code=400, detail="Invalid base64 image payload.") from exc


def _extract_image(messages: list[ChatMessage]) -> tuple[bytes, str]:
    image_payload: tuple[bytes, str] | None = None

    for message in messages:
        content = message.content
        if not isinstance(content, list):
            continue

        for item in content:
            if item.type == "image_url" and image_payload is None:
                image_payload = _decode_data_url(item.image_url.url)

    if image_payload is None:
        raise HTTPException(status_code=400, detail="Expected a user image in messages.")

    return image_payload


def _chat_response(model: str | None, text: str) -> dict[str, object]:
    created = int(time.time())
    return {
        "id": f"chatcmpl-{uuid4().hex}",
        "object": "chat.completion",
        "created": created,
        "model": model or "mac-ocr",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": text,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }


@app.post("/ocr")
async def process_image(
    file: UploadFile = File(...),
) -> dict[str, object]:
    path = Path(gettempdir()) / f"{uuid4().hex}.jpg"
    try:
        path.write_bytes(await file.read())
        return ocr_image_path(path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        path.unlink(missing_ok=True)


@app.post("/v1/chat/completions")
async def chat_completions(payload: ChatCompletionRequest) -> dict[str, object]:
    if payload.stream:
        raise HTTPException(status_code=400, detail="streaming is not supported")

    image_bytes, suffix = _extract_image(payload.messages)
    path = Path(gettempdir()) / f"{uuid4().hex}{suffix}"
    try:
        path.write_bytes(image_bytes)
        result = ocr_image_path(path)
        text = str(result.get("text", "") or "").strip()
        return _chat_response(payload.model, text)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        path.unlink(missing_ok=True)


def main() -> None:
    import uvicorn
    uvicorn.run("src.app:app", host=HOST, port=PORT, reload=True)
