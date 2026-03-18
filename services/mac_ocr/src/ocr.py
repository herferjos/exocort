from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import objc


@dataclass(frozen=True)
class OcrLine:
    text: str
    confidence: float
    x: float
    y: float
    width: float
    height: float

    def to_dict(self) -> dict[str, str | float]:
        return asdict(self)


@dataclass(frozen=True)
class OcrRow:
    index: int
    text: str
    x: float
    y: float
    width: float
    height: float
    confidence: float
    line_count: int

    def to_dict(self) -> dict[str, str | int | float]:
        return asdict(self)


@dataclass(frozen=True)
class OcrBlock:
    index: int
    text: str
    x: float
    y: float
    width: float
    height: float
    confidence: float
    row_count: int

    def to_dict(self) -> dict[str, str | int | float]:
        return asdict(self)


def _vision():
    import Vision

    return Vision


def ocr_image_path(path: Path, mode: str = "fast") -> dict[str, object]:
    image_path = path.expanduser().resolve()
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    lines = _recognize_lines_from_path(image_path, mode=mode)
    rows = _build_rows(lines)
    blocks = _build_blocks(rows)
    return {
        "text": "\n".join(item.text for item in rows),
    }


def _recognize_lines_from_path(path: Path, mode: str) -> list[OcrLine]:
    image_url = objc.lookUpClass("NSURL").fileURLWithPath_(str(path))
    handler = _vision().VNImageRequestHandler.alloc().initWithURL_options_(image_url, {})
    return _recognize_lines(handler, mode=mode)


def _recognize_lines(handler, *, mode: str) -> list[OcrLine]:
    Vision = _vision()
    lines: list[OcrLine] = []
    seen: set[tuple[str, int, int, int, int]] = set()

    for use_correction in (True, False):
        request = Vision.VNRecognizeTextRequest.alloc().initWithCompletionHandler_(None)
        recognition_level = (
            getattr(Vision, "VNRequestTextRecognitionLevelFast", 0)
            if mode == "fast"
            else getattr(Vision, "VNRequestTextRecognitionLevelAccurate", 1)
        )
        request.setRecognitionLevel_(recognition_level)
        request.setUsesLanguageCorrection_(use_correction)
        if hasattr(request, "setAutomaticallyDetectsLanguage_"):
            request.setAutomaticallyDetectsLanguage_(True)
        if hasattr(request, "setMinimumTextHeight_"):
            request.setMinimumTextHeight_(0.0)

        success, error = handler.performRequests_error_([request], None)
        if not success:
            message = str(error) if error is not None else "unknown Vision error"
            raise RuntimeError(f"Vision OCR failed: {message}")

        for observation in request.results() or []:
            candidates = observation.topCandidates_(1)
            if not candidates:
                continue

            candidate = candidates[0]
            text = _clean_text(str(candidate.string() or ""))
            if not text:
                continue

            box = observation.boundingBox()
            line = OcrLine(
                text=text,
                confidence=float(candidate.confidence()),
                x=float(box.origin.x),
                y=float(box.origin.y),
                width=float(box.size.width),
                height=float(box.size.height),
            )
            if not _should_keep_line(line):
                continue

            key = (
                line.text,
                round(line.x * 1000),
                round(line.y * 1000),
                round(line.width * 1000),
                round(line.height * 1000),
            )
            if key in seen:
                continue
            seen.add(key)
            lines.append(line)

    return sorted(lines, key=lambda item: (-item.y, item.x, -item.confidence))


def _build_rows(lines: list[OcrLine]) -> list[OcrRow]:
    if not lines:
        return []

    horizontal_bands: list[list[OcrLine]] = []
    for line in sorted(lines, key=lambda item: (-item.y, item.x)):
        placed = False
        for band in horizontal_bands:
            anchor = band[0]
            y_delta = abs(anchor.y - line.y)
            threshold = max(anchor.height, line.height, 0.012) * 0.8
            if y_delta <= threshold:
                band.append(line)
                placed = True
                break
        if not placed:
            horizontal_bands.append([line])

    rows: list[OcrRow] = []
    index = 1
    for band in horizontal_bands:
        for segment in _split_row_segments(sorted(band, key=lambda item: item.x)):
            text = _join_texts([item.text for item in segment])
            if not text:
                continue
            x1 = min(item.x for item in segment)
            y1 = min(item.y for item in segment)
            x2 = max(item.x + item.width for item in segment)
            y2 = max(item.y + item.height for item in segment)
            rows.append(
                OcrRow(
                    index=index,
                    text=text,
                    x=x1,
                    y=y1,
                    width=x2 - x1,
                    height=y2 - y1,
                    confidence=sum(item.confidence for item in segment) / len(segment),
                    line_count=len(segment),
                )
            )
            index += 1

    return rows


def _build_blocks(rows: list[OcrRow]) -> list[OcrBlock]:
    if not rows:
        return []

    grouped: list[list[OcrRow]] = [[rows[0]]]
    for row in rows[1:]:
        previous = grouped[-1][-1]
        vertical_gap = previous.y - (row.y + row.height)
        left_delta = abs(previous.x - row.x)
        horizontal_overlap = min(previous.x + previous.width, row.x + row.width) - max(
            previous.x, row.x
        )
        same_block = (
            vertical_gap <= max(previous.height, row.height, 0.015) * 1.6
            and left_delta <= 0.05
            and horizontal_overlap >= -0.02
        )
        if same_block:
            grouped[-1].append(row)
        else:
            grouped.append([row])

    blocks: list[OcrBlock] = []
    for index, group in enumerate(grouped, start=1):
        text = "\n".join(item.text for item in group).strip()
        if not text:
            continue
        x1 = min(item.x for item in group)
        y1 = min(item.y for item in group)
        x2 = max(item.x + item.width for item in group)
        y2 = max(item.y + item.height for item in group)
        blocks.append(
            OcrBlock(
                index=index,
                text=text,
                x=x1,
                y=y1,
                width=x2 - x1,
                height=y2 - y1,
                confidence=sum(item.confidence for item in group) / len(group),
                row_count=len(group),
            )
        )

    return blocks


def _split_row_segments(lines: list[OcrLine]) -> list[list[OcrLine]]:
    if not lines:
        return []

    segments: list[list[OcrLine]] = [[lines[0]]]
    for line in lines[1:]:
        previous = segments[-1][-1]
        gap = line.x - (previous.x + previous.width)
        threshold = max(previous.height, line.height, 0.012) * 2.5
        if gap > threshold:
            segments.append([line])
        else:
            segments[-1].append(line)
    return segments


def _join_texts(parts: list[str]) -> str:
    merged: list[str] = []
    for part in parts:
        text = _clean_text(part)
        if not text:
            continue
        if not merged:
            merged.append(text)
            continue
        if _should_glue(merged[-1], text):
            merged[-1] = merged[-1] + text
        else:
            merged.append(text)
    return " ".join(merged).strip()


def _should_glue(left: str, right: str) -> bool:
    if left.endswith(("/", "-", "_", "(", "[", "{", "#")):
        return True
    if right.startswith(("/", "-", "_", ")", "]", "}", ".", ",", ":", ";")):
        return True
    if len(right) == 1 and not right.isalnum():
        return True
    return False


def _clean_text(text: str) -> str:
    compact = " ".join(text.replace("\n", " ").split()).strip()
    if not compact:
        return ""
    if compact in {"|", "||", "lll", "[]", "()", "{}", "..."}:
        return ""
    if len(compact) <= 2 and not any(char.isalnum() for char in compact):
        return ""
    return compact


def _should_keep_line(line: OcrLine) -> bool:
    if line.confidence >= 0.6:
        return True
    if any(char.isalnum() for char in line.text):
        return True
    if len(line.text) >= 3:
        return True
    return (line.width * line.height) >= 0.002
