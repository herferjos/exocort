"""Unit tests for exocort runner."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


pytestmark = pytest.mark.unit


def test_runner_exits_when_nothing_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("exocort.settings.collector_enabled", lambda: False)
    monkeypatch.setattr("exocort.settings.audio_capturer_enabled", lambda: False)
    monkeypatch.setattr("exocort.settings.screen_capturer_enabled", lambda: False)

    from exocort.runner import main

    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1


def test_runner_starts_collector_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("exocort.settings.collector_enabled", lambda: True)
    monkeypatch.setattr("exocort.settings.audio_capturer_enabled", lambda: False)
    monkeypatch.setattr("exocort.settings.screen_capturer_enabled", lambda: False)

    procs: list[MagicMock] = []

    def fake_popen(*args: object, **kwargs: object) -> MagicMock:
        p = MagicMock()
        # First poll: loop continues; second: loop exits; third (in shutdown): still running -> terminate()
        p.poll.side_effect = [None, 0, None]
        procs.append(p)
        return p

    with (
        patch("exocort.runner.subprocess.Popen", side_effect=fake_popen),
        patch("exocort.runner.time.sleep"),
    ):
        from exocort.runner import main

        main()

    assert len(procs) == 1
    procs[0].terminate.assert_called()
