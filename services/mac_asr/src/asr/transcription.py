from __future__ import annotations

import threading
import time
from pathlib import Path

import Foundation
import objc
import Speech

from common.models.asr import TranscriptionResponse
from common.utils.logs import get_logger

log = get_logger("mac_asr", "asr")
_RECOGNIZER_CACHE: dict[str, objc.pyobjc_object] = {}
_RECOGNIZER_LOCK = threading.Lock()


def transcribe_audio_file(
    path: Path,
    *,
    locale: str,
    timeout_s: float,
) -> TranscriptionResponse:
    locale_id = (locale or "").strip()
    log.debug(
        "Starting ASR transcription | path=%s | locale=%s | timeout_s=%s",
        path,
        locale_id,
        timeout_s,
    )
    with _RECOGNIZER_LOCK:
        recognizer = _RECOGNIZER_CACHE.get(locale_id)

    if recognizer is None:
        if locale_id:
            try:
                ns_locale = Foundation.NSLocale.alloc().initWithLocaleIdentifier_(locale_id)
                recognizer = Speech.SFSpeechRecognizer.alloc().initWithLocale_(ns_locale)
            except Exception:
                recognizer = None
        else:
            recognizer = Speech.SFSpeechRecognizer.alloc().init()

        if recognizer is not None:
            with _RECOGNIZER_LOCK:
                recognizer = _RECOGNIZER_CACHE.setdefault(locale_id, recognizer)
                log.debug("Created and cached recognizer | locale=%s", locale_id)
    else:
        log.debug("Reusing cached recognizer | locale=%s", locale_id)

    if recognizer is None:
        raise RuntimeError(f"Speech recognizer is not available for locale '{locale_id}'.")

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

    log.debug(
        "Finished ASR transcription | path=%s | locale=%s | text_len=%s",
        path,
        locale_id,
        len(state["text"]),
    )
    return TranscriptionResponse(
        text=str(state["text"]).strip(),
        language=locale_id,
        duration=None,
    )
