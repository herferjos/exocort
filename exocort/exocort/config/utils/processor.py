from __future__ import annotations

from pathlib import Path

from ..models.processor import ProcessorSettings
from .asr import parse_asr_settings
from .common import as_mapping, parse_content_filter_settings, resolve_path
from .notes import parse_notes_settings
from .ocr import parse_ocr_settings


def parse_processor_settings(data: object, config_dir: Path) -> ProcessorSettings:
    mapping = as_mapping(data, "processor")
    content_filter_data = mapping.get("content_filter", mapping.get("sensitive_data", {}))
    return ProcessorSettings(
        watch_dir=resolve_path(mapping.get("watch_dir", "captures"), config_dir),
        output_dir=resolve_path(mapping.get("output_dir", "captures/processed"), config_dir),
        ocr=parse_ocr_settings(mapping.get("ocr", {}), "processor.ocr"),
        asr=parse_asr_settings(mapping.get("asr", {}), "processor.asr"),
        content_filter=parse_content_filter_settings(content_filter_data),
        notes=parse_notes_settings(mapping.get("notes", {}), config_dir),
    )
