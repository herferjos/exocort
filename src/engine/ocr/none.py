from pathlib import Path

from .base import OcrEngine


class NullOcr(OcrEngine):
    def extract_text(self, path: Path) -> str:
        return ""
