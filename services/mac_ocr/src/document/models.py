from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class OcrDocumentPayload(BaseModel):
    type: Literal["image_url"]
    image_url: str


class OcrRequestPayload(BaseModel):
    model: str | None = None
    document: OcrDocumentPayload
