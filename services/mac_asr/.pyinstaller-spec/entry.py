"""PyInstaller-only entry point.

Wraps app.main with the adaptations required for a frozen bundle:
- multiprocessing.freeze_support() to absorb subprocess re-execs.
- Line-buffered stdout/stderr so argparse and uvicorn output reach the TTY.
- argparse-based CLI that overrides config.yaml values.
- Force reload=False (uvicorn's reloader can't run inside a PyInstaller bundle)
  and pass the FastAPI app object directly so uvicorn does not try to import it.
"""
from __future__ import annotations

import multiprocessing
import sys

multiprocessing.freeze_support()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)

import argparse
import dataclasses

import uvicorn

from app.main import app
from common.utils.ports import kill_processes_on_port
from src.asr.permissions import ensure_speech_permission
from src.config.settings import load_settings


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="mac-asr-service",
        description=(
            "Mac ASR — speech-recognition HTTP API backed by Apple Speech framework.\n\n"
            "Locale examples: 'auto' (detect per-request), 'es-ES', 'en-US', 'fr-FR'."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    srv = p.add_argument_group("server")
    srv.add_argument("--host", default=None, metavar="HOST",
                     help="Bind host (default: 127.0.0.1)")
    srv.add_argument("--port", type=int, default=None, metavar="PORT",
                     help="Bind port (default: 9092)")
    srv.add_argument("--log-level", default=None,
                     choices=["debug", "info", "warning", "error", "critical"],
                     help="Uvicorn log level (default: info)")

    asr = p.add_argument_group("transcription")
    asr.add_argument("--locale", default=None, metavar="LOCALE",
                     help="Transcription locale or 'auto' for per-request detection (default: auto)")
    asr.add_argument("--default-locale", default=None, metavar="LOCALE",
                     help="Fallback locale used when detection is inconclusive (default: es)")
    asr.add_argument("--timeout", type=float, default=None, metavar="SECONDS",
                     help="Max seconds to wait for a transcription result (default: 30)")
    asr.add_argument("--no-permission-prompt", action="store_true", default=False,
                     help="Skip the macOS speech-recognition permission prompt")

    det = p.add_argument_group("language detection (faster-whisper)")
    det.add_argument("--detect-model", default=None,
                     choices=["tiny", "base", "small", "medium"],
                     help="Whisper model used for language detection (default: tiny)")
    det.add_argument("--detect-device", default=None,
                     choices=["cpu", "cuda"],
                     help="Device for the detection model (default: cpu)")
    det.add_argument("--detect-compute-type", default=None,
                     choices=["int8", "float16", "float32"],
                     help="Compute type for the detection model (default: int8)")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    settings = load_settings()
    overrides: dict = {"reload": False}
    if args.host is not None:
        overrides["host"] = args.host
    if args.port is not None:
        overrides["port"] = args.port
    if args.log_level is not None:
        overrides["log_level"] = args.log_level
    if args.locale is not None:
        overrides["locale"] = args.locale
    if args.default_locale is not None:
        overrides["default_locale"] = args.default_locale
    if args.timeout is not None:
        overrides["transcription_timeout_s"] = args.timeout
    if args.no_permission_prompt:
        overrides["prompt_permission"] = False
    if args.detect_model is not None:
        overrides["detect_model"] = args.detect_model
    if args.detect_device is not None:
        overrides["detect_device"] = args.detect_device
    if args.detect_compute_type is not None:
        overrides["detect_compute_type"] = args.detect_compute_type
    settings = dataclasses.replace(settings, **overrides)

    if not ensure_speech_permission(prompt=settings.prompt_permission):
        raise RuntimeError("Speech recognition permission is required.")
    kill_processes_on_port(settings.port)
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )


if __name__ == "__main__":
    main()
