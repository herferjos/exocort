from __future__ import annotations

from pathlib import Path

from .asr import resolve_locale
from .config import load_settings
from .lang_detect import detect_language


def resolve_request_locale(path: Path, language: str | None) -> str:
    settings = load_settings()
    explicit_language = (language or "").strip()
    explicit_language_lower = explicit_language.lower()
    detect_requested = (
        explicit_language_lower == "auto" or settings.locale.strip().lower() == "auto"
    )
    if explicit_language_lower == "auto":
        explicit_language = ""

    detected_code = None
    detected_probability = None
    if not explicit_language and detect_requested:
        detected_code, detected_probability = detect_language(path)
        if detected_probability is None:
            return resolve_locale(None, settings.default_locale)
        if detected_probability < settings.detect_discard_min_prob:
            return ""
        if detected_probability < settings.detect_default_min_prob:
            return resolve_locale(None, settings.default_locale)
    return resolve_locale(detected_code, explicit_language)


def transcription_text(result: object) -> str:
    text = str(getattr(result, "text", "") or "").strip()
    if not text and hasattr(result, "to_dict"):
        text = str(result.to_dict().get("text", "") or "").strip()
    return text
