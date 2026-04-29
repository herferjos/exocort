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

from app.main import app, log
from common.utils.ports import kill_processes_on_port
from src.config.settings import load_settings


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="llama-cpp-service",
        description="Llama.cpp — OpenAI-compatible chat completion HTTP API.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    srv = p.add_argument_group("server")
    srv.add_argument("--host", default=None, metavar="HOST",
                     help="Bind host (default: 127.0.0.1)")
    srv.add_argument("--port", type=int, default=None, metavar="PORT",
                     help="Bind port (default: 9100)")
    srv.add_argument("--log-level", default=None,
                     choices=["debug", "info", "warning", "error", "critical"],
                     help="Uvicorn log level (default: debug)")

    model = p.add_argument_group("model")
    model.add_argument("--model-id", default=None, metavar="REPO_ID",
                       help="HuggingFace repo or local path of the GGUF model")
    model.add_argument("--quantization", default=None, metavar="QUANT",
                       help="GGUF quantisation tag, e.g. Q4_K_M, Q8_0")
    model.add_argument("--model-dir", default=None, metavar="DIR",
                       help="Directory where model files are cached (default: ./llms)")
    model.add_argument("--chat-format", default=None, metavar="FORMAT",
                       help="llama-cpp-python chat format or path to a .jinja template")

    runtime = p.add_argument_group("runtime")
    runtime.add_argument("--n-ctx", type=int, default=None, metavar="TOKENS",
                         help="Context window size in tokens (default: 15000)")
    runtime.add_argument("--n-gpu-layers", type=int, default=None, metavar="N",
                         help="Number of layers to offload to GPU; 0 = CPU only (default: 24)")
    runtime.add_argument("--n-threads", type=int, default=None, metavar="N",
                         help="CPU threads for inference (default: 4)")
    runtime.add_argument("--n-batch", type=int, default=None, metavar="N",
                         help="Prompt processing batch size (default: 512)")
    runtime.add_argument("--temperature", type=float, default=None, metavar="FLOAT",
                         help="Sampling temperature (default: 0.5)")
    runtime.add_argument("--seed", type=int, default=None, metavar="INT",
                         help="RNG seed; -1 for random (default: 42)")
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
    if args.model_id is not None:
        overrides["model_id"] = args.model_id
    if args.quantization is not None:
        overrides["quantization"] = args.quantization
    if args.model_dir is not None:
        overrides["model_dir"] = Path(args.model_dir)
    if args.chat_format is not None:
        overrides["chat_format"] = args.chat_format
    if args.n_ctx is not None:
        overrides["n_ctx"] = args.n_ctx
    if args.n_gpu_layers is not None:
        overrides["n_gpu_layers"] = args.n_gpu_layers
    if args.n_threads is not None:
        overrides["n_threads"] = args.n_threads
    if args.n_batch is not None:
        overrides["n_batch"] = args.n_batch
    if args.temperature is not None:
        overrides["temperature"] = args.temperature
    if args.seed is not None:
        overrides["seed"] = args.seed
    settings = dataclasses.replace(settings, **overrides)

    kill_processes_on_port(settings.port)
    log.info(
        "Starting llama.cpp app | host=%s | port=%s | reload=%s | log_level=%s",
        settings.host,
        settings.port,
        settings.reload,
        settings.log_level,
    )
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )


if __name__ == "__main__":
    main()
