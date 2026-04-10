from __future__ import annotations

import argparse
import threading
from pathlib import Path

from exocort.config import ExocortSettings, load_config

DEFAULT_CONFIG_PATH = Path("config.yaml")


def run(config: ExocortSettings) -> None:
    services: list[threading.Thread] = []

    if config.audio.enabled:
        from exocort.capturer.audio.capture import audio_loop

        services.append(
            threading.Thread(
                target=audio_loop,
                args=(config.audio,),
                name="audio-capturer",
            )
        )

    if config.screen.enabled:
        from exocort.capturer.screen.capture import screenshot_loop

        services.append(
            threading.Thread(
                target=screenshot_loop,
                args=(config.screen,),
                name="screen-capturer",
            )
        )

    if config.processor.enabled:
        from exocort.processor.service import processing_loop

        services.append(
            threading.Thread(
                target=processing_loop,
                args=(config.processor,),
                name="file-processor",
            )
        )

    if not services:
        print("[exocort] no services enabled, nothing to run.")
        return

    for service in services:
        service.start()

    print(f"[exocort] running {len(services)} service(s)")

    for service in services:
        service.join()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Exocort capturers from a YAML config.")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to YAML config file (default: {DEFAULT_CONFIG_PATH})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    run(config)


if __name__ == "__main__":
    main()
