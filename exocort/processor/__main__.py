"""Module entrypoint for the processor package."""

from __future__ import annotations

import logging
import multiprocessing
import signal
import sys

from exocort import settings

from .config import load_app_config, load_processor_config
from .engine import build_worker_specs, prepare_runtime_dirs, run_worker_spec

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(
        level=settings.log_level(),
        format="%(asctime)s | %(levelname)s | %(processName)s | %(name)s | %(message)s",
    )

    logger.info("Starting processor")
    app_config = load_app_config()
    processor_config = load_processor_config()
    logger.info(
        "Processor config loaded: mode=%s stages=%s poll_interval_s=%s max_concurrent_tasks=%s dry_run=%s",
        processor_config.execution_mode,
        len(processor_config.stages),
        processor_config.poll_interval_s,
        processor_config.max_concurrent_tasks,
        processor_config.dry_run,
    )
    prepare_runtime_dirs(processor_config)
    semaphore = multiprocessing.Semaphore(processor_config.max_concurrent_tasks)

    worker_specs = build_worker_specs(processor_config)
    logger.info("Worker specs prepared: %s", ", ".join(spec["name"] for spec in worker_specs))
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
