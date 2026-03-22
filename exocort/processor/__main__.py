"""Module entrypoint for the processor package."""

from __future__ import annotations

import logging
import multiprocessing
import signal
import sys

from exocort import settings

from .config import load_app_config, load_processor_config
from .engine import build_worker_specs, run_worker_spec


def main() -> None:
    logging.basicConfig(
        level=settings.log_level(),
        format="%(asctime)s | %(levelname)s | %(processName)s | %(name)s | %(message)s",
    )

    app_config = load_app_config()
    processor_config = load_processor_config()
    semaphore = multiprocessing.Semaphore(processor_config.max_concurrent_tasks)

    worker_specs = build_worker_specs(processor_config)
    processes: list[multiprocessing.Process] = []

    for spec in worker_specs:
        process = multiprocessing.Process(
            target=run_worker_spec,
            args=(processor_config, app_config, semaphore, spec),
            name=spec["name"],
        )
        processes.append(process)
        process.start()
        logging.info("Started worker: %s", spec["name"])

    def shutdown(signum: int, frame: object) -> None:
        del signum, frame
        logging.info("Shutting down workers...")
        for process in processes:
            process.terminate()
        for process in processes:
            process.join()
        logging.info("Shutdown complete.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    for process in processes:
        process.join()


if __name__ == "__main__":
    main()
