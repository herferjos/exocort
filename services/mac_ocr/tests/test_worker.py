from __future__ import annotations

import asyncio
import base64

import pytest
from fastapi import HTTPException

from common.models.ocr import OcrResponse
from services.mac_ocr.app.api.v1.endpoints.ocr import process_image
from common.models.ocr import OcrDocumentPayload, OcrRequestPayload


pytestmark = [pytest.mark.service, pytest.mark.unit, pytest.mark.ocr]


def test_process_image_accepts_litellm_image_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    image_bytes = b"fake-image"
    image_url = "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii")

    def fake_ocr_image_path(path):
        captured["bytes"] = path.read_bytes()
        captured["suffix"] = path.suffix
        return OcrResponse(
            pages=[{"index": 0, "markdown": "hello world", "images": []}],
            model="mac-ocr",
            usage_info={"pages_processed": 1, "doc_size_bytes": len(image_bytes)},
            document_annotation=None,
            object="ocr",
        )

    monkeypatch.setattr(
        "services.mac_ocr.app.api.v1.endpoints.ocr.ocr_image_path",
        fake_ocr_image_path,
    )

    payload = OcrRequestPayload(
        model="mistral/mistral-ocr-latest",
        document=OcrDocumentPayload(type="image_url", image_url=image_url),
    )
    response = asyncio.run(process_image(payload))

    assert response.object == "ocr"
    assert captured["bytes"] == image_bytes
    assert captured["suffix"] == ".png"


def test_process_image_rejects_non_data_uri() -> None:
    payload = OcrRequestPayload(
        model="mistral/mistral-ocr-latest",
        document=OcrDocumentPayload(type="image_url", image_url="https://example.com/image.png"),
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(process_image(payload))

    assert exc.value.status_code == 400
