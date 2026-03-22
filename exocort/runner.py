"""Run enabled Exocort components from the shared config file."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

# Project root for cwd of child processes
_project_root = Path(__file__).resolve().parent.parent


def main() -> None:
    from exocort import settings

    collector_enabled = settings.collector_enabled()
    audio_enabled = settings.audio_capturer_enabled()
    screen_enabled = settings.screen_capturer_enabled()
    processor_enabled = settings.processor_enabled()

    if not any((collector_enabled, audio_enabled, screen_enabled, processor_enabled)):
        print(
            "Nothing to run. Enable at least one component in config/exocort.toml under [runtime].",
            file=sys.stderr,
        )
        sys.exit(1)

    procs: list[subprocess.Popen[bytes]] = []

    def shutdown() -> None:
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()

    def handler(_signum: int, _frame: object) -> None:
        shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)

    env = os.environ.copy()

    if collector_enabled:
        procs.append(
            subprocess.Popen(
                [sys.executable, "-m", "exocort.collector.app"],
                cwd=str(_project_root),
                env=env,
                stdout=None,
                stderr=None,
            )
        )
        time.sleep(1.5)

    if processor_enabled:
        procs.append(
            subprocess.Popen(
                [sys.executable, "-m", "exocort.processor"],
                cwd=str(_project_root),
                env=env,
                stdout=None,
                stderr=None,
            )
        )

    if audio_enabled:
        procs.append(
            subprocess.Popen(
                [sys.executable, "-m", "exocort.capturer.audio"],
                cwd=str(_project_root),
                env=env,
                stdout=None,
                stderr=None,
            )
        )

    if screen_enabled:
        procs.append(
            subprocess.Popen(
                [sys.executable, "-m", "exocort.capturer.screen"],
                cwd=str(_project_root),
                env=env,
                stdout=None,
                stderr=None,
            )
        )

    try:
        while any(p.poll() is None for p in procs):
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        shutdown()
