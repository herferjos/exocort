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
import os
import sys
from pathlib import Path

multiprocessing.freeze_support()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)

if getattr(sys, "frozen", False) and "EXOCORT_CONFIG_PATH" not in os.environ:
    _external = Path(sys.executable).resolve().parent / "config.yaml"
    _meipass = getattr(sys, "_MEIPASS", None)
    _bundled = Path(_meipass) / "config.yaml" if _meipass else None
    if _external.exists():
        os.environ["EXOCORT_CONFIG_PATH"] = str(_external)
    elif _bundled and _bundled.exists():
        os.environ["EXOCORT_CONFIG_PATH"] = str(_bundled)

import argparse
import dataclasses

import uvicorn

from app.main import app
from common.utils.ports import kill_processes_on_port
from src.config.settings import load_settings


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="faster-whisper-service",
        description="Faster Whisper — speech transcription HTTP API.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    srv = p.add_argument_group("server")
    srv.add_argument("--host", default=None, metavar="HOST",
                     help="Bind host (default: 127.0.0.1)")
    srv.add_argument("--port", type=int, default=None, metavar="PORT",
                     help="Bind port (default: 9000)")
    srv.add_argument("--log-level", default=None,
                     choices=["debug", "info", "warning", "error", "critical"],
                     help="Uvicorn log level (default: info)")

    model = p.add_argument_group("model")
    model.add_argument("--model-size", default=None,
                       choices=["tiny", "base", "small", "medium", "large-v2", "large-v3"],
                       help="Whisper model size to load (default: medium)")
    model.add_argument("--model-path", default=None, metavar="DIR",
                       help="Directory where model files are stored (default: ./models)")
    model.add_argument("--device", default=None,
                       choices=["cpu", "cuda"],
                       help="Compute device (default: cpu)")
    model.add_argument("--compute-type", default=None,
                       choices=["int8", "float16", "float32"],
                       help="Quantisation type (default: int8)")
    model.add_argument("--beam-size", type=int, default=None, metavar="N",
                       help="Beam search width (default: 5)")
    model.add_argument("--language", default=None, metavar="CODE",
                       help="Force a language code (e.g. 'en', 'es') or omit for auto-detection")
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
    if args.model_size is not None:
        overrides["model_size"] = args.model_size
    if args.model_path is not None:
        overrides["model_path"] = Path(args.model_path)
    if args.device is not None:
        overrides["device"] = args.device
    if args.compute_type is not None:
        overrides["compute_type"] = args.compute_type
    if args.beam_size is not None:
        overrides["beam_size"] = args.beam_size
    if args.language is not None:
        overrides["language"] = args.language
    settings = dataclasses.replace(settings, **overrides)

    kill_processes_on_port(settings.port)
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )


if __name__ == "__main__":
    main()
