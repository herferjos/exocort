from __future__ import annotations

import logging
import sys

from exocort import settings

from .agent import AudiocapturerAgent
from .models import Settings


def main() -> None:
    logging.basicConfig(
        level=settings.log_level(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    AudiocapturerAgent(Settings.from_env()).run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
