"""Artifact rendering helpers."""

from __future__ import annotations

import json
import logging
from typing import Any

from .models import ArtifactEnvelope
from .utils import utc_iso

logger = logging.getLogger(__name__)


def render_markdown(envelope: ArtifactEnvelope | dict[str, Any]) -> str:
    value = envelope if isinstance(envelope, ArtifactEnvelope) else ArtifactEnvelope.from_dict(envelope)
    frontmatter = {
        "id": value.id,
        "timestamp": value.timestamp,
        "source_ids": value.source_ids,
        "updated_at": utc_iso(),
    }
    lines = ["---"]
    for key, item in frontmatter.items():
        lines.append(f"{key}: {json.dumps(item, ensure_ascii=False)}")
    lines.extend(
        [
            "---",
            "",
            f"# {value.id}",
            "",
            "```json",
            json.dumps(value.to_dict(), ensure_ascii=False, indent=2, sort_keys=True),
            "```",
            "",
        ]
    )
    logger.debug("Rendered markdown artifact: id=%s timestamp=%s", value.id, value.timestamp)
    return "\n".join(lines)
