from __future__ import annotations

from pathlib import Path

import Vision
import objc

from .models import OcrLine


def ocr_image_path(path: Path) -> dict[str, object]:
    image_path = path.expanduser().resolve()
    if not image_path.exists():
        raise FileNotFoundError(image_path)

    lines = _recognize_lines_from_path(image_path)
    text = " ".join(line.text for line in lines if line.text).strip()
    return {
        "text": text,
        "lines": [line.__dict__ for line in lines],
        "model": "vision",
        "usage": {
            "input_pixels": None,
            "output_tokens": 0,
            "total_tokens": 0,
        },
    }


def _recognize_lines_from_path(path: Path) -> list[OcrLine]:
    image_url = objc.lookUpClass("NSURL").fileURLWithPath_(str(path))
    handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(image_url, {})
    return _recognize_lines(handler)


def _recognize_lines(handler) -> list[OcrLine]:
    lines: list[OcrLine] = []
    seen: set[tuple[str, int, int, int, int]] = set()

    def callback(request, error) -> None:
        if error is not None:
            raise RuntimeError(str(error))
        results = getattr(request, "results", None) or []
        for result in results:
            observations = getattr(result, "topCandidates_", None)
            if observations is not None:
                observations = observations(1)
            if not observations:
                continue
            candidate = observations[0]
            text = str(candidate.string() or "").strip()
            if not text:
                continue
            box = getattr(candidate, "boundingBox", None)
            if box is None:
                continue
            key = (
                text,
                int(box.origin.x * 10_000),
                int(box.origin.y * 10_000),
                int(box.size.width * 10_000),
                int(box.size.height * 10_000),
            )
            if key in seen:
                continue
            seen.add(key)
            lines.append(
                OcrLine(
                    text=text,
                    confidence=float(getattr(candidate, "confidence", 0.0)),
                    x=float(box.origin.x),
                    y=float(box.origin.y),
                    width=float(box.size.width),
                    height=float(box.size.height),
                )
            )

    request = Vision.VNRecognizeTextRequest.alloc().initWithCompletionHandler_(callback)
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(True)
    if hasattr(request, "setAutomaticallyDetectsLanguage_"):
        request.setAutomaticallyDetectsLanguage_(True)
    handler.performRequests_error_([request], None)
    return lines


__all__ = ["OcrLine", "ocr_image_path"]
