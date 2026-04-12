from __future__ import annotations

import argparse
import threading
from pathlib import Path

from dotenv import load_dotenv

from exocort.config import ExocortSettings, load_config
from exocort.logs import configure_logging, get_logger

DEFAULT_CONFIG_PATH = Path("config.yaml")
log = get_logger("runner")


def run(config: ExocortSettings) -> None:
    services: list[threading.Thread] = []
    capturer = config.capturer
    processor = config.processor

    if capturer.audio.enabled:
        from exocort.capturer.audio.capture import audio_loop

        services.append(
            threading.Thread(
                target=audio_loop,
                args=(capturer.audio,),
                name="audio-capturer",
            )
        )

    if capturer.screen.enabled:
        from exocort.capturer.screen.capture import screenshot_loop

        services.append(
            threading.Thread(
                target=screenshot_loop,
                args=(capturer.screen,),
                name="screen-capturer",
            )
        )

    if processor.ocr.enabled or processor.asr.enabled or processor.notes.enabled:
        from exocort.processor.service import processing_loop

        services.append(
            threading.Thread(
                target=processing_loop,
                args=(config,),
                name="file-processor",
            )
        )

    if not services:
        log.info("no services enabled, nothing to run.")
        return

    for service in services:
        service.start()

    log.info("running %s service(s)", len(services))

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
    load_dotenv()
    configure_logging()
    args = parse_args()
    config = load_config(args.config)
    run(config)


if __name__ == "__main__":
    main()
