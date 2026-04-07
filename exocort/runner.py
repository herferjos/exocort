from __future__ import annotations

import argparse
import threading
from collections.abc import Callable
from pathlib import Path

from exocort.config import ExocortConfig, load_config

DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.toml")


def build_services(config: ExocortConfig) -> list[threading.Thread]:
    services: list[threading.Thread] = []

    if config.audio.enabled:
        from exocort.capturer.audio import audio_loop

        services.append(
            _build_thread(
                "audio-capturer",
                audio_loop,
                config.audio_capture,
            )
        )

    if config.screen.enabled:
        from exocort.capturer.screen import screenshot_loop

        services.append(
            _build_thread(
                "screen-capturer",
                screenshot_loop,
                config.screen_capture,
            )
        )

    return services


def run(config: ExocortConfig) -> None:
    services = build_services(config)

    if not services:
        print("[exocort] no capturers enabled, nothing to run.")
        return

    for service in services:
        service.start()

    print(f"[exocort] running {len(services)} capturer(s)")

    for service in services:
        service.join()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Exocort capturers from a TOML config.")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to TOML config file (default: {DEFAULT_CONFIG_PATH})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    run(config)


def _build_thread(name: str, target: Callable[[object], None], config: object) -> threading.Thread:
    return threading.Thread(target=target, args=(config,), name=name)


if __name__ == "__main__":
    main()
