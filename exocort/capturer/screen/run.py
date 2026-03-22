from __future__ import annotations

import logging
import sys

from exocort import settings

from .capture import Screencapturer
from .models import ScreenSettings


def main() -> None:
    logging.basicConfig(
        level=settings.log_level(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    cfg = ScreenSettings.from_env()
    Screencapturer(cfg).run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
