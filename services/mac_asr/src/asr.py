from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

import objc


@dataclass(frozen=True)
class Transcription:
    text: str
    locale: str
    is_final: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "text": self.text,
            "locale": self.locale,
            "is_final": self.is_final,
        }


def _speech():
    import Speech

    return Speech


def _foundation():
    import Foundation

    return Foundation


def _avfoundation():
    import AVFoundation

    return AVFoundation


def ensure_microphone_permission(prompt: bool = False) -> bool:
    AVFoundation = _avfoundation()
    media_type = getattr(AVFoundation, "AVMediaTypeAudio", "soun")
    status = int(
        AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(media_type)
    )
    authorized = int(getattr(AVFoundation, "AVAuthorizationStatusAuthorized", 3))
    not_determined = int(getattr(AVFoundation, "AVAuthorizationStatusNotDetermined", 0))

    if status == authorized:
        return True
    if status != not_determined or not prompt:
        return False

    done = threading.Event()
    granted = {"value": False}

    def handler(value: bool) -> None:
        granted["value"] = bool(value)
        done.set()

    AVFoundation.AVCaptureDevice.requestAccessForMediaType_completionHandler_(
        media_type, handler
    )
    done.wait(30.0)
    return bool(granted["value"])


def ensure_speech_permission(prompt: bool = False) -> bool:
    Speech = _speech()
    status = int(Speech.SFSpeechRecognizer.authorizationStatus())
    authorized = int(
        getattr(Speech, "SFSpeechRecognizerAuthorizationStatusAuthorized", 3)
    )
    not_determined = int(
        getattr(Speech, "SFSpeechRecognizerAuthorizationStatusNotDetermined", 0)
    )

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


def ensure_permissions(prompt: bool = False) -> dict[str, bool]:
    return {
        "microphone": ensure_microphone_permission(prompt=prompt),
        "speech": ensure_speech_permission(prompt=prompt),
    }


def transcribe_pcm_bytes(
    pcm_bytes: bytes,
    *,
    sample_rate: int,
    locale: str,
    timeout_s: float,
) -> Transcription:
    with NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        path = Path(tmp_file.name)

    try:
        _write_wav_file(path, pcm_bytes, sample_rate)
        return transcribe_audio_file(path, locale=locale, timeout_s=timeout_s)
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def transcribe_audio_file(path: Path, *, locale: str, timeout_s: float) -> Transcription:
    command = [
        sys.executable,
        "-m",
        "src.transcribe_file",
        str(path),
        locale,
        str(timeout_s),
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=max(5.0, timeout_s + 5.0),
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        if stderr:
            return Transcription(text="", locale=locale, is_final=False)
        return Transcription(text="", locale=locale, is_final=False)
    payload = json.loads(completed.stdout)
    return Transcription(
        text=str(payload.get("text", "")).strip(),
        locale=str(payload.get("locale", locale)),
        is_final=bool(payload.get("is_final", False)),
    )


def transcribe_wav_file(path: Path, *, locale: str, timeout_s: float) -> Transcription:
    return transcribe_audio_file(path, locale=locale, timeout_s=timeout_s)


def transcribe_audio_file_direct(
    path: Path,
    *,
    locale: str,
    timeout_s: float,
) -> Transcription:
    Foundation = _foundation()
    Speech = _speech()

    recognizer = Speech.SFSpeechRecognizer.alloc().init()
    if recognizer is None:
        raise RuntimeError("Speech recognizer is not available.")

    request = Speech.SFSpeechURLRecognitionRequest.alloc().initWithURL_(
        objc.lookUpClass("NSURL").fileURLWithPath_(str(path))
    )
    if hasattr(request, "setShouldReportPartialResults_"):
        request.setShouldReportPartialResults_(False)

    state = {
        "text": "",
        "is_final": False,
        "done": False,
        "error": "",
    }

    def handler(result, error) -> None:
        if result is not None:
            state["text"] = str(result.bestTranscription().formattedString() or "")
            state["is_final"] = bool(getattr(result, "isFinal", lambda: False)())
            if state["is_final"]:
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

    return Transcription(
        text=str(state["text"]).strip(),
        locale=locale,
        is_final=bool(state["is_final"]),
    )


def transcribe_wav_file_direct(
    path: Path,
    *,
    locale: str,
    timeout_s: float,
) -> Transcription:
    return transcribe_audio_file_direct(path, locale=locale, timeout_s=timeout_s)


def _write_wav_file(path: Path, pcm_bytes: bytes, sample_rate: int) -> None:
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)
