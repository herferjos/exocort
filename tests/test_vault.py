"""Unit tests for collector vault (save_to_tmp, write_vault_record, remove_tmp)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from exocort.collector import vault


pytestmark = pytest.mark.unit


def test_save_to_tmp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("COLLECTOR_TMP_DIR", str(tmp_path))
    path = vault.save_to_tmp(b"content", "audio", "2025-03-15", "ts_abc", ".wav")
    assert path == tmp_path / "audio" / "2025-03-15" / "ts_abc.wav"
    assert path.read_bytes() == b"content"


def test_write_vault_record(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("COLLECTOR_VAULT_DIR", str(tmp_path))
    path = vault.write_vault_record(
        date="2025-03-15",
        timestamp_iso="2025-03-15T12:00:00.000Z",
        type_="audio",
        id_="seg1",
        meta={"segment_id": "seg1"},
        responses=[vault.normalize_vault_response("http://x", "openai", True, 200, "raw body", "extracted text")],
    )
    assert path == tmp_path / "2025-03-15" / "2025-03-15T12-00-00.000Z_audio_seg1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["type"] == "audio"
    assert data["id"] == "seg1"
    assert len(data["responses"]) == 1
    r = data["responses"][0]
    assert r["url"] == "http://x"
    assert r["provider"] == "openai"
    assert r["ok"] is True
    assert r["status"] == 200
    assert r["text"] == "extracted text"
    assert r["raw"] == "raw body"


def test_remove_tmp(tmp_path: Path) -> None:
    f = tmp_path / "file.wav"
    f.write_bytes(b"x")
    assert f.exists()
    vault.remove_tmp(f)
    assert not f.exists()


def test_remove_tmp_missing_ok(tmp_path: Path) -> None:
    f = tmp_path / "missing.wav"
    vault.remove_tmp(f)
    assert not f.exists()
