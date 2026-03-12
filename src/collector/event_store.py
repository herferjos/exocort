from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .util import json_line


@dataclass
class EventStore:
    data_dir: Path

    def append(self, event: dict) -> Path:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        out_dir = self.data_dir / "events"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{day}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json_line(event) + "\n")
        return path
