from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import objc

from .config import LOCALE


@dataclass(frozen=True)
class Transcription:
    text: str
    locale: str

    def to_dict(self) -> dict[str, object]:
        return {"text": self.text, "locale": self.locale}


def _speech():
    import Speech
    return Speech


def _foundation():
    import Foundation
    return Foundation


def _is_no_speech_error(error_message: str) -> bool:
    msg = (error_message or "").lower()
    return ("no speech detected" in msg) or (
        "kafassistanterrordomain" in msg and "code=1110" in msg
    )


def ensure_speech_permission(prompt: bool = False) -> bool:
    import threading
    Speech = _speech()
    status = int(Speech.SFSpeechRecognizer.authorizationStatus())
    authorized = int(getattr(Speech, "SFSpeechRecognizerAuthorizationStatusAuthorized", 3))
    not_determined = int(getattr(Speech, "SFSpeechRecognizerAuthorizationStatusNotDetermined", 0))

    if status == authorized:
        return True
    if status != not_determined or not prompt:
        return False

    done = threading.Event()
    granted = {"value": False}

    def handler(value) -> None:
        granted["value"] = int(value) == authorized
        done.set()

    Speech.SFSpeechRecognizer.requestAuthorization_(handler)
    done.wait(30.0)
    return bool(granted["value"])


def transcribe_audio_file(path: Path, *, locale: str, timeout_s: float) -> Transcription:
    Foundation = _foundation()
    Speech = _speech()

    locale_id = (locale or "").strip()
    recognizer = None
    if locale_id:
        try:
            ns_locale = Foundation.NSLocale.alloc().initWithLocaleIdentifier_(locale_id)
            recognizer = Speech.SFSpeechRecognizer.alloc().initWithLocale_(ns_locale)
        except Exception:
            recognizer = None
    if recognizer is None:
        recognizer = Speech.SFSpeechRecognizer.alloc().init()
    if recognizer is None:
        raise RuntimeError("Speech recognizer is not available.")
    resolved_locale = locale_id
    try:
        recognizer_locale = recognizer.locale()
        if recognizer_locale is not None:
            resolved_locale = str(recognizer_locale.localeIdentifier() or resolved_locale)
    except Exception:
        pass

    request = Speech.SFSpeechURLRecognitionRequest.alloc().initWithURL_(
        objc.lookUpClass("NSURL").fileURLWithPath_(str(path))
    )
    if hasattr(request, "setShouldReportPartialResults_"):
        request.setShouldReportPartialResults_(False)

    state = {"text": "", "done": False, "error": ""}

    def handler(result, error) -> None:
        if result is not None:
            state["text"] = str(result.bestTranscription().formattedString() or "")
            state["done"] = True
            return
        if error is not None:
            state["error"] = str(error)
            state["done"] = True

    task = recognizer.recognitionTaskWithRequest_resultHandler_(request, handler)
    run_loop = Foundation.NSRunLoop.currentRunLoop()
    deadline = time.monotonic() + max(1.0, timeout_s)

    while not state["done"] and time.monotonic() < deadline:
        run_loop.runUntilDate_(Foundation.NSDate.dateWithTimeIntervalSinceNow_(0.05))

    del task

    if state["error"] and not state["text"]:
        raise RuntimeError(state["error"])

    return Transcription(text=str(state["text"]).strip(), locale=resolved_locale)


def _supported_locale_ids() -> list[str]:
    Speech = _speech()
    locales = Speech.SFSpeechRecognizer.supportedLocales()
    if locales is None:
        return []
    try:
        locale_ids = {str(locale.localeIdentifier()) for locale in locales if locale is not None}
    except Exception:
        locale_ids = set()
        for locale in list(locales):
            try:
                locale_ids.add(str(locale.localeIdentifier()))
            except Exception:
                continue
    return sorted(locale_ids)


def _language_code_for_locale(locale_id: str) -> str | None:
    Foundation = _foundation()
    try:
        ns_locale = Foundation.NSLocale.alloc().initWithLocaleIdentifier_(locale_id)
    except Exception:
        return None
    code = None
    try:
        if hasattr(ns_locale, "languageCode"):
            code = ns_locale.languageCode()
        if not code:
            code = ns_locale.objectForKey_(Foundation.NSLocaleLanguageCode)
    except Exception:
        code = None
    return str(code).lower() if code else None


def resolve_locale(detected_code: str | None, explicit: str | None) -> str:
    explicit_locale = (explicit or "").strip()
    if explicit_locale:
        if explicit_locale.lower() == "auto":
            explicit_locale = ""
        else:
            return explicit_locale

    configured = (LOCALE or "").strip()
    if configured.lower() == "auto":
        configured = ""

    if explicit_locale:
        return explicit_locale

    detected = (detected_code or "").strip().lower()
    if not detected:
        return configured
    if configured:
        configured_code = _language_code_for_locale(configured)
        if configured_code and configured_code == detected:
            return configured

    supported = _supported_locale_ids()
    for locale_id in supported:
        if _language_code_for_locale(locale_id) == detected:
            return locale_id

    return configured


__all__ = [
    "Transcription",
    "_is_no_speech_error",
    "ensure_speech_permission",
    "transcribe_audio_file",
    "resolve_locale",
]
