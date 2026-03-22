"""Frontmost app / window detection (platform)."""

from __future__ import annotations

try:
    import pywinctl
except ImportError:
    pywinctl = None


def frontmost_app() -> tuple[str, str, int]:
    """Cross-platform: app name, bundle_id (empty), pid for the active window."""
    if pywinctl is None:
        return "", "", 0
    try:
        win = pywinctl.getActiveWindow()
        if win is None:
            return "", "", 0
        name = win.getAppName() or win.title or ""
        pid = getattr(win, "getPID", lambda: None)()
        pid = int(pid) if pid is not None else 0
        return (name or "").strip(), "", pid
    except Exception:
        return "", "", 0
