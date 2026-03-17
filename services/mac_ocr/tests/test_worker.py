from __future__ import annotations

import asyncio
import io

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from src.app import process_image


pytestmark = [pytest.mark.service, pytest.mark.unit, pytest.mark.ocr]


def test_process_image_returns_ocr_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.app.ocr_image_path",
        lambda path: {
            "text": "hello world",
        },
    )
    upload = UploadFile(filename="screen.png", file=io.BytesIO(b"fake-image"))

    payload = asyncio.run(process_image(file=upload))

    assert payload["text"] == "hello world"
    assert list(payload.keys()) == ["text"]


def test_process_image_wraps_missing_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.app.ocr_image_path",
        lambda path: (_ for _ in ()).throw(FileNotFoundError("missing")),
    )
    upload = UploadFile(filename="screen.png", file=io.BytesIO(b"fake-image"))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(process_image(file=upload))

    assert exc.value.status_code == 404
    assert exc.value.detail == "missing"
