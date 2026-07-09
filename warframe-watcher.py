#!/usr/bin/env python3
"""
warframe-watcher.py - polls for Warframe.x64.exe and restarts wfinfo
whenever Warframe starts or restarts, so wfinfo's X11 window handle stays fresh.
"""
import os
import subprocess
import time
from pathlib import Path
from paths import DATA_DIR, WFINFO_DIR
WFINFO_BIN = WFINFO_DIR / "target/release/orbiter"
LOG_FILE = DATA_DIR / "orbiter.log"
WATCHER_LOG = DATA_DIR / "watcher.log"

POLL_INTERVAL = 5         # seconds between Warframe-PID checks
WAIT_BEFORE_RESTART = 6   # grace period so Warframe's window is rendered before we capture

def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(WATCHER_LOG, "a") as f:
        f.write(f"[{ts}] {msg}\n")

from platform_utils import get_pid, kill_processes, launch_detached, clean_env_for_launch


def get_warframe_pid():
    # On Windows Warframe runs natively; on Linux via Proton
    for pattern in ["Warframe.x64.exe", "Warframe.exe"]:
        pid = get_pid(pattern)
        if pid:
            return pid
    return None

def restart_wfinfo():
    log("Restarting orbiter")
    kill_processes("target/release/orbiter")
    kill_processes("orbiter.exe")
    time.sleep(1.0)
    try:
        clean_env = clean_env_for_launch()
        launch_detached([str(WFINFO_BIN)], cwd=WFINFO_DIR, env=clean_env, log_file=LOG_FILE)
        log("orbiter started")
    except Exception as e:
        log(f"failed to start orbiter: {e}")

def main():
    log("=== watcher started ===")
    last_pid = None
    pending_restart_at = None

    while True:
        current = get_warframe_pid()
        if current != last_pid:
            if current is not None:
                if last_pid is None:
                    log(f"Warframe started (PID {current})")
                else:
                    log(f"Warframe restarted ({last_pid} -> {current})")
                pending_restart_at = time.time() + WAIT_BEFORE_RESTART
            else:
                log(f"Warframe closed (was PID {last_pid})")
                pending_restart_at = None
            last_pid = current

        if pending_restart_at and time.time() >= pending_restart_at:
            restart_wfinfo()
            pending_restart_at = None

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()