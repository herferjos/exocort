import abc
from pathlib import Path


class OcrEngine(abc.ABC):
    @abc.abstractmethod
    def extract_text(self, path: Path) -> str:
        ...
