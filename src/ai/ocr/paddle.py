import logging
from pathlib import Path

from .base import OcrEngine

log = logging.getLogger("ai.ocr.paddle")


class PaddleOcrEngine(OcrEngine):
    _engines = None
    _langs_key = None

    def __init__(self, languages: list[str]):
        self.languages = languages

    def _get_engines(self):
        if self.__class__._engines is not None and self.__class__._langs_key == ",".join(self.languages):
            return self.__class__._engines
        from paddleocr import PaddleOCR

        engines = [PaddleOCR(lang=lang) for lang in self.languages]
        self.__class__._engines = engines
        self.__class__._langs_key = ",".join(self.languages)
        return engines

    def extract_text(self, path: Path) -> str:
        try:
            engines = self._get_engines()
            chunks: list[str] = []
            for engine in engines:
                result = engine.ocr(str(path), cls=False)
                for line in result or []:
                    for _, text_info in line:
                        text = text_info[0] if isinstance(text_info, (list, tuple)) else ""
                        if text:
                            chunks.append(str(text))
            return "\n".join(chunks).strip()
        except Exception as exc:
            log.warning("Paddle OCR failed | path=%s | error=%s", path, exc)
            return ""
