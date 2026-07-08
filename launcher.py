#!/usr/bin/env python3
"""
launcher.py — Cross-platform launcher for Kieda's Orbiter.

Replaces control-panel.sh, launch-overlay.sh, and launch-wfinfo.sh.
Works on Linux, Windows, and macOS.

Usage:
    python launcher.py app        # Launch the main GUI (missing-parts.py)
    python launcher.py overlay    # Launch the relic reward overlay
    python launcher.py detector   # Launch the Rust OCR detector binary
    python launcher.py watcher    # Launch the warframe-watcher process manager
"""

import os
import sys
import subprocess
from pathlib import Path

WFINFO_DIR = Path(__file__).parent
VENV = WFINFO_DIR / ".venv"

IS_WINDOWS = sys.platform == "win32"
IS_LINUX   = sys.platform.startswith("linux")
IS_MAC     = sys.platform == "darwin"

# ── Python executable inside venv ────────────────────────────────────────
if IS_WINDOWS:
    PYTHON = VENV / "Scripts" / "python.exe"
else:
    PYTHON = VENV / "bin" / "python"

if not PYTHON.exists():
    # Fallback: use current interpreter (useful during initial setup)
    PYTHON = Path(sys.executable)

# ── Rust detector binary ──────────────────────────────────────────────────
if IS_WINDOWS:
    DETECTOR = WFINFO_DIR / "target" / "release" / "orbiter.exe"
    if not DETECTOR.exists():
        DETECTOR = WFINFO_DIR / "orbiter.exe"  # installed alongside app
else:
    DETECTOR = WFINFO_DIR / "target" / "release" / "orbiter"
    if not DETECTOR.exists():
        DETECTOR = WFINFO_DIR / "target" / "release" / "wfinfo"


def _find_qt_lib_dirs() -> list[str]:
    """Find all PySide6 Qt lib directories for LD_LIBRARY_PATH (Linux/Mac)."""
    dirs = []
    for lib_base in VENV.glob("lib*/python*/site-packages/PySide6/Qt/lib"):
        if lib_base.is_dir():
            dirs.append(str(lib_base))
    return dirs


def _build_env() -> dict:
    """Build the environment for child processes."""
    env = os.environ.copy()

    if IS_LINUX or IS_MAC:
        uid = os.getuid()
        runtime_dir = f"/run/user/{uid}"
        host_bus    = f"unix:path={runtime_dir}/bus"

        # Force host DBus — strip any Flatpak/sandbox contamination
        env["DBUS_SESSION_BUS_ADDRESS"] = host_bus
        env["XDG_RUNTIME_DIR"]          = runtime_dir
        env["XDG_DATA_HOME"]            = str(Path.home() / ".local/share")
        env["XDG_CACHE_HOME"]           = str(Path.home() / ".cache")
        env["XDG_SESSION_TYPE"]         = "wayland"
        env.setdefault("WAYLAND_DISPLAY",     "wayland-0")
        env.setdefault("XDG_CURRENT_DESKTOP", "KDE")
        for k in ["FLATPAK_ID", "FLATPAK_SANDBOX_EXPORT_PATH"]:
            env.pop(k, None)

        # Qt platform plugin
        if env.get("WAYLAND_DISPLAY"):
            env["QT_QPA_PLATFORM"] = "wayland"
        elif env.get("DISPLAY"):
            env["QT_QPA_PLATFORM"] = "xcb"
        else:
            env["QT_QPA_PLATFORM"] = "offscreen"

        # PySide6 needs its own Qt libs on the library path
        qt_dirs = _find_qt_lib_dirs()
        if qt_dirs:
            existing = env.get("LD_LIBRARY_PATH", "")
            env["LD_LIBRARY_PATH"] = ":".join(qt_dirs + ([existing] if existing else []))

        # Host system libs for the Rust binary (Bazzite/immutable distros)
        host_libs = "/run/host/usr/lib64:/run/host/usr/lib"
        existing = env.get("LD_LIBRARY_PATH", "")
        if host_libs not in existing:
            env["LD_LIBRARY_PATH"] = host_libs + (":" + existing if existing else "")

        # Block notify-send (steals Warframe focus via desktop notification)
        import tempfile, stat
        fake_bin = Path(tempfile.mkdtemp())
        notify_fake = fake_bin / "notify-send"
        notify_fake.write_text("#!/bin/sh\nexit 0\n")
        notify_fake.chmod(notify_fake.stat().st_mode | stat.S_IEXEC)
        env["PATH"] = str(fake_bin) + ":" + env.get("PATH", "")

    elif IS_WINDOWS:
        # On Windows Qt finds its own plugins; no LD_LIBRARY_PATH needed
        pass

    return env


def launch_app():
    """Launch the main GUI application."""
    env = _build_env()
    os.execve(str(PYTHON), [str(PYTHON), str(WFINFO_DIR / "missing-parts.py")], env)


def launch_overlay():
    """Launch the relic reward overlay."""
    env = _build_env()
    os.execve(str(PYTHON), [str(PYTHON), str(WFINFO_DIR / "overlay.py")], env)


def launch_detector(extra_args: list = None):
    """Launch the Rust OCR detector binary."""
    if not DETECTOR.exists():
        print(f"ERROR: Rust detector binary not found at {DETECTOR}", file=sys.stderr)
        print("Build it with: cargo build --release --bin orbiter", file=sys.stderr)
        sys.exit(1)

    env = _build_env()
    cmd = [str(DETECTOR)] + (extra_args or [])
    os.execve(str(DETECTOR), cmd, env)


def launch_watcher():
    """Launch the warframe-watcher process manager."""
    env = _build_env()
    os.execve(str(PYTHON), [str(PYTHON), str(WFINFO_DIR / "warframe-watcher.py")], env)


# ── Entry point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Default: launch the main app
        launch_app()

    mode = sys.argv[1].lower()
    if mode == "app":
        launch_app()
    elif mode == "overlay":
        launch_overlay()
    elif mode in ("detector", "orbiter"):
        launch_detector(sys.argv[2:])
    elif mode == "watcher":
        launch_watcher()
    else:
        print(f"Unknown mode: {mode}", file=sys.stderr)
        print("Usage: launcher.py [app|overlay|detector|watcher]", file=sys.stderr)
        sys.exit(1)
