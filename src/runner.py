import logging
import os
import shlex
import sys
import threading
import time

import uvicorn

import settings
from collector import app as collector_app
from capture import audio as audio_capture
from capture import screen as screen_capture
from processor import cli as processor_cli


def _run_collector() -> None:
    config = uvicorn.Config(
        collector_app.app,
        host=settings.collector_host(),
        port=settings.collector_port(),
        log_config=None,
        access_log=True,
    )
    server = uvicorn.Server(config)
    server.run()


def _run_audio() -> None:
    audio_capture.main()


def _run_screen() -> None:
    screen_capture.main()


def _run_processor() -> None:
    args_raw = os.getenv("PROCESSOR_ARGS", "").strip()
    argv = ["exocort-processor"]
    if args_raw:
        argv.extend(shlex.split(args_raw))
    original_argv = sys.argv[:]
    try:
        sys.argv = argv
        processor_cli.main()
    finally:
        sys.argv = original_argv


def _start_thread(name: str, target) -> threading.Thread:
    thread = threading.Thread(target=target, name=name, daemon=True)
    thread.start()
    return thread


def main() -> int:
    logging.basicConfig(
        level=os.getenv("RUNNER_LOG_LEVEL", "INFO"),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    log = logging.getLogger("runner")

    log.info("Starting Exocort runner")

    threads = []
    threads.append(_start_thread("collector", _run_collector))

    if settings.audio_capture_enabled():
        log.info("Audio capture enabled")
        threads.append(_start_thread("audio", _run_audio))
    else:
        log.info("Audio capture disabled")

    if settings.screen_capture_enabled():
        log.info("Screen capture enabled")
        threads.append(_start_thread("screen", _run_screen))
    else:
        log.info("Screen capture disabled")

    if settings.processor_enabled():
        log.info("Processor enabled (one-shot)")
        threads.append(_start_thread("processor", _run_processor))
    else:
        log.info("Processor disabled")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Runner stopped by user")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
