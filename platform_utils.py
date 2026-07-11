"""
platform_utils.py — cross-platform process management utilities.

Replaces pgrep/pkill/nohup shell calls so the app works on Windows too.
All process operations go through psutil, which works identically on
Linux, Windows, and macOS.
"""

import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import psutil

IS_WINDOWS = sys.platform == "win32"
IS_LINUX   = sys.platform.startswith("linux")
IS_MAC     = sys.platform == "darwin"


# ── Process detection ─────────────────────────────────────────────────────

def find_processes(pattern: str) -> List[psutil.Process]:
    """Return all running processes whose cmdline contains `pattern`."""
    matches = []
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = " ".join(proc.info["cmdline"] or [])
            if pattern in cmdline:
                matches.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return matches


def is_running(pattern: str) -> bool:
    """Return True if any process whose cmdline contains `pattern` is running."""
    return len(find_processes(pattern)) > 0


def get_pid(pattern: str) -> Optional[int]:
    """Return the PID of the first process matching `pattern`, or None."""
    procs = find_processes(pattern)
    return procs[0].pid if procs else None


# ── Process control ───────────────────────────────────────────────────────

def kill_processes(pattern: str, timeout: float = 5.0) -> int:
    """
    Kill all processes whose cmdline contains `pattern`.
    Returns the number of processes killed.
    Tries SIGTERM first, then SIGKILL after `timeout` seconds.
    """
    procs = find_processes(pattern)
    for p in procs:
        try:
            p.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    # Wait for graceful exit
    _, alive = psutil.wait_procs(procs, timeout=timeout)
    for p in alive:
        try:
            p.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return len(procs)


# ── Process launching ─────────────────────────────────────────────────────

def launch_detached(
    cmd: List[str],
    cwd: Optional[Path] = None,
    env: Optional[dict] = None,
    log_file: Optional[Path] = None,
) -> subprocess.Popen:
    """
    Launch a process detached from the parent (equivalent of nohup ... & disown).
    Works on Linux, Windows, and macOS.
    """
    kwargs = dict(
        cwd=str(cwd) if cwd else None,
        env=env,
        stdin=subprocess.DEVNULL,
    )

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = open(log_file, "ab")
        kwargs["stdout"] = fh
        kwargs["stderr"] = fh
    else:
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.DEVNULL

    if IS_WINDOWS:
        # DETACHED_PROCESS does NOT suppress a console — for a console-
        # subsystem child (python.exe, orbiter.exe) it actually makes
        # Windows allocate a brand new blank one, since a detached console
        # process still needs *a* console. CREATE_NO_WINDOW is the flag
        # that means "no console window, ever, for this process."
        CREATE_NO_WINDOW = 0x08000000
        kwargs["creationflags"] = CREATE_NO_WINDOW
    else:
        # On Linux/Mac, start_new_session detaches from the terminal
        kwargs["start_new_session"] = True

    return subprocess.Popen(cmd, **kwargs)


def clean_env_for_launch(extra: Optional[dict] = None) -> dict:
    """
    Return a clean environment dict for launching child processes.
    On Linux/Mac: strips Flatpak sandbox vars, forces correct XDG/DBus paths.
    On Windows: returns os.environ copy (no sandbox issue).
    """
    env = os.environ.copy()

    if IS_LINUX or IS_MAC:
        uid = os.getuid()
        runtime_dir = f"/run/user/{uid}"
        host_bus = f"unix:path={runtime_dir}/bus"

        # Override with correct host values — strip Flatpak contamination
        env["DBUS_SESSION_BUS_ADDRESS"] = host_bus
        env["XDG_RUNTIME_DIR"] = runtime_dir
        env["XDG_DATA_HOME"] = str(Path.home() / ".local/share")
        env["XDG_CACHE_HOME"] = str(Path.home() / ".cache")
        env.setdefault("WAYLAND_DISPLAY", "wayland-0")
        env.setdefault("XDG_CURRENT_DESKTOP", "KDE")
        env["XDG_SESSION_TYPE"] = "wayland"
        # Remove Flatpak-specific vars
        for key in ["FLATPAK_ID", "FLATPAK_SANDBOX_EXPORT_PATH"]:
            env.pop(key, None)

    if extra:
        env.update(extra)
    return env
