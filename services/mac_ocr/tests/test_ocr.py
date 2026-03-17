from __future__ import annotations

from pathlib import Path

import pytest

from src.ocr import OcrLine, ocr_image_path


pytestmark = [pytest.mark.service, pytest.mark.unit, pytest.mark.ocr]


def test_ocr_image_path_returns_text_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "frame.png"
    image_path.write_bytes(b"fake-image")

    monkeypatch.setattr(
        "src.ocr._recognize_lines_from_path",
        lambda path: [
            OcrLine(
                text="hello world",
                confidence=0.99,
                x=0.1,
                y=0.8,
                width=0.3,
                height=0.05,
            )
        ],
    )

    payload = ocr_image_path(image_path)

    assert payload["text"] == "hello world"
    assert list(payload.keys()) == ["text"]


def test_ocr_image_path_missing_file_raises(tmp_path: Path) -> None:
    missing = tmp_path / "missing.png"

    with pytest.raises(FileNotFoundError):
        ocr_image_path(missing)
