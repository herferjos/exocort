from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class StoredSnapshot:
    path: Path
    captured_at: str


class SnapshotStore:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir

    def write(self, payload: dict[str, object], captured_at: datetime) -> StoredSnapshot:
        day = captured_at.strftime("%Y-%m-%d")
        time_part = captured_at.strftime("%H-%M-%S")
        day_dir = self.root_dir / day
        day_dir.mkdir(parents=True, exist_ok=True)

        captured_at_iso = captured_at.isoformat()
        structured = dict(payload)
        structured["captured_at"] = captured_at_iso
        text = str(payload.get("structured_text", "") or "")

        out = {"structured": structured, "text": text}
        path = day_dir / f"{time_part}.json"
        path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        return StoredSnapshot(path=path, captured_at=captured_at_iso)
