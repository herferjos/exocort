from __future__ import annotations

from pathlib import Path

import pytest

from services.faster_whisper.config import load_settings


pytestmark = [pytest.mark.service, pytest.mark.unit]


def test_load_settings_reads_toml(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        'model_path = "small"\n'
        'device = "cpu"\n'
        'compute_type = "int8"\n'
        'vad_filter = true\n'
        'beam_size = 7\n'
        'language = "en"\n',
        encoding="utf-8",
    )

    settings = load_settings(cfg)
    assert settings.model_path == "small"
    assert settings.beam_size == 7
    assert settings.language == "en"


def test_load_settings_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_settings(tmp_path / "missing.toml")
