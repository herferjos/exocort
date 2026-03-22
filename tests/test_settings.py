"""Unit tests for exocort.settings."""

from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.unit


def _write_config(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


def test_log_level_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = tmp_path / "exocort.toml"
    _write_config(cfg, "")
    monkeypatch.setenv("EXOCORT_CONFIG", str(cfg))
    from exocort import settings

    assert settings.log_level() == "INFO"


def test_log_level_from_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = tmp_path / "exocort.toml"
    _write_config(cfg, '[runtime]\nlog_level = "DEBUG"\n')
    monkeypatch.setenv("EXOCORT_CONFIG", str(cfg))
    from exocort import settings

    assert settings.log_level() == "DEBUG"


def test_audio_capturer_enabled_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = tmp_path / "exocort.toml"
    _write_config(cfg, "")
    monkeypatch.setenv("EXOCORT_CONFIG", str(cfg))
    from exocort import settings

    assert settings.audio_capturer_enabled() is False


def test_audio_capturer_enabled_true(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = tmp_path / "exocort.toml"
    _write_config(cfg, "[runtime]\nenable_audio_capturer = true\n")
    monkeypatch.setenv("EXOCORT_CONFIG", str(cfg))
    from exocort import settings

    assert settings.audio_capturer_enabled() is True


def test_screen_capturer_enabled_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = tmp_path / "exocort.toml"
    _write_config(cfg, "")
    monkeypatch.setenv("EXOCORT_CONFIG", str(cfg))
    from exocort import settings

    assert settings.screen_capturer_enabled() is False


def test_collector_enabled_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = tmp_path / "exocort.toml"
    _write_config(cfg, "")
    monkeypatch.setenv("EXOCORT_CONFIG", str(cfg))
    from exocort import settings

    assert settings.collector_enabled() is True


def test_collector_enabled_off(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = tmp_path / "exocort.toml"
    _write_config(cfg, "[runtime]\nenable_collector = false\n")
    monkeypatch.setenv("EXOCORT_CONFIG", str(cfg))
    from exocort import settings

    assert settings.collector_enabled() is False


def test_audio_capturer_spool_dir_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = tmp_path / "exocort.toml"
    _write_config(cfg, "")
    monkeypatch.setenv("EXOCORT_CONFIG", str(cfg))
    from exocort import settings

    p = settings.audio_capturer_spool_dir()
    assert "tmp" in p.parts and "audio" in p.parts


def test_collector_tmp_dir_from_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = tmp_path / "exocort.toml"
    _write_config(cfg, '[collector]\ntmp_dir = "custom"\n')
    monkeypatch.setenv("EXOCORT_CONFIG", str(cfg))
    monkeypatch.chdir(tmp_path)
    from exocort import settings

    assert settings.collector_tmp_dir() == (tmp_path / "custom").resolve()


def test_collector_vault_dir_from_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = tmp_path / "exocort.toml"
    _write_config(cfg, '[collector]\nvault_dir = "vault-data"\n')
    monkeypatch.setenv("EXOCORT_CONFIG", str(cfg))
    monkeypatch.chdir(tmp_path)
    from exocort import settings

    assert settings.collector_vault_dir() == (tmp_path / "vault-data").resolve()
