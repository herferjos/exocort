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
from src.config.settings import load_settings


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="mac-ocr-service",
        description="Mac OCR — image OCR HTTP API backed by Apple Vision framework.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--host", default=None, metavar="HOST",
                   help="Bind host (config.yaml default: 127.0.0.1)")
    p.add_argument("--port", type=int, default=None, metavar="PORT",
                   help="Bind port (config.yaml default: 9093)")
    p.add_argument("--log-level", default=None,
                   choices=["debug", "info", "warning", "error", "critical"],
                   help="Uvicorn log level")
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
