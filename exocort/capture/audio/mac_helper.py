from __future__ import annotations

import json
import logging
import os
import platform
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("audio_capture.mac_helper")


@dataclass(frozen=True)
class MacHelperHeader:
    sample_rate: int
    channels: int
    format: str


class MacAudioHelper:
    def __init__(self, proc: subprocess.Popen, header: MacHelperHeader):
        self.proc = proc
        self.header = header
        self._buffer = b""
        self._stderr_thread = threading.Thread(
            target=self._drain_stderr,
            name="mac-audio-helper-stderr",
            daemon=True,
        )
        self._stderr_thread.start()

    def read_exact(self, size: int) -> bytes | None:
        if self.proc.stdout is None:
            return None
        while len(self._buffer) < size:
            chunk = self.proc.stdout.read(size - len(self._buffer))
            if not chunk:
                return None
            self._buffer += chunk
        data, self._buffer = self._buffer[:size], self._buffer[size:]
        return data

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self._stderr_thread.join(timeout=1.0)

    def _drain_stderr(self) -> None:
        if self.proc.stderr is None:
            return
        for line in iter(self.proc.stderr.readline, b""):
            text = line.decode("utf-8", errors="ignore").strip()
            if text:
                log.info("mac helper | %s", text)


def is_macos() -> bool:
    return platform.system().lower() == "darwin"


def resolve_helper_path(override: str | None) -> Path | None:
    if override:
        return Path(override).expanduser().resolve()
    candidate = Path(__file__).resolve().with_name("mac_audio_helper")
    if candidate.exists():
        return candidate
    swift_candidate = Path(__file__).resolve().with_name("mac_audio_helper.swift")
    if swift_candidate.exists():
        return swift_candidate
    return None


def start_helper(*, sample_rate: int, channels: int, helper_path: str | None) -> MacAudioHelper:
    path = resolve_helper_path(helper_path)
    if path is None:
        raise RuntimeError("macOS helper not found")

    path = _ensure_executable_or_fallback(path)
    if path is None:
        raise RuntimeError("macOS helper not executable")

    _codesign_adhoc(path)
    cmd = _build_command(path, sample_rate=sample_rate, channels=channels)
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
        env=_clean_env(),
    )

    header = _read_header(proc)
    if header.format != "s16le":
        proc.terminate()
        raise RuntimeError(f"Unsupported helper format: {header.format}")
    return MacAudioHelper(proc, header)


def _build_command(path: Path, *, sample_rate: int, channels: int) -> list[str]:
    if path.suffix == ".swift":
        return ["/usr/bin/swift", str(path), "--sample-rate", str(sample_rate), "--channels", str(channels)]
    return [str(path), "--sample-rate", str(sample_rate), "--channels", str(channels)]


def _read_header(proc: subprocess.Popen) -> MacHelperHeader:
    if proc.stdout is None:
        raise RuntimeError("macOS helper missing stdout")
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError("macOS helper failed to emit header")
    return parse_header_line(line)


def parse_header_line(line: bytes) -> MacHelperHeader:
    try:
        data = json.loads(line.decode("utf-8"))
        return MacHelperHeader(
            sample_rate=int(data.get("sample_rate", 0) or 0),
            channels=int(data.get("channels", 0) or 0),
            format=str(data.get("format", "")),
        )
    except Exception as exc:
        raise RuntimeError("macOS helper header invalid") from exc


def _clean_env() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    return env


def _ensure_executable_or_fallback(path: Path) -> Path | None:
    if path.suffix == ".swift":
        return path
    if path.exists() and os.access(path, os.X_OK):
        return path
    if path.exists():
        try:
            mode = path.stat().st_mode
            path.chmod(mode | 0o111)
        except Exception:
            log.warning("macOS helper not executable and chmod failed | path=%s", path)
        if os.access(path, os.X_OK):
            return path
    swift_fallback = path.with_suffix(".swift")
    if swift_fallback.exists():
        log.warning("macOS helper binary unavailable; falling back to swift script | path=%s", swift_fallback)
        return swift_fallback
    return None


def _codesign_adhoc(path: Path) -> None:
    if path.suffix == ".swift":
        return
    try:
        subprocess.run(
            ["/usr/bin/codesign", "-s", "-", "--force", "--timestamp=none", str(path)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        log.debug("Ad-hoc codesign failed | path=%s", path)
