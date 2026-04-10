from __future__ import annotations

import logging


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")


def get_logger(*parts: str) -> logging.Logger:
    logger = logging.getLogger("exocort")
    if not parts:
        return logger
    return logger.getChild(".".join(parts))
