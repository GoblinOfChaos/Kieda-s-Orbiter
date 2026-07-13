#!/usr/bin/env python3

"""WFInfo Control Panel - status, maintenance, and tools."""

import json
from PySide6.QtWidgets import QScrollArea
import os
import subprocess
import sys
import time
from glob import glob
from pathlib import Path

import sys as _wfi_sys
from pathlib import Path as _WfiPath
_wfi_sys.path.insert(0, str(_WfiPath(__file__).parent))
from theme import WFINFO_STYLESHEET, BG_CARD, BG_PANEL, BG_INPUT, GOLD, GOLD_BRIGHT, FG, FG_DIM, BORDER
from health import HealthWidget

from PySide6.QtCore import Qt, QTimer, QProcess, QSettings
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QGroupBox, QFormLayout, QTextEdit, QMessageBox,
)
from paths import DATA_DIR, WFINFO_DIR, get_ee_log_path, get_inventory_path

WFINFO_ICON = str(WFINFO_DIR / ("orbiter.ico" if sys.platform == "win32" else "orbiter.svg"))

HOME = Path.home()
HELPER_SRC = HOME / "helper-src"
OWNED_FILE = WFINFO_DIR / "owned_items.json"
WFCD_CACHE = WFINFO_DIR / "wfcd_all_cache.json"
OVERLAY_SCRIPT = WFINFO_DIR / "overlay.py"
VENV_PYTHON = WFINFO_DIR / (".venv/Scripts/python.exe" if sys.platform == "win32" else ".venv/bin/python")
STATE_FILE = DATA_DIR / "latest-detection.json"
LOG_FILE = DATA_DIR / "overlay.log"


from platform_utils import is_running, kill_processes


def pgrep(pattern):
    return is_running(pattern)


def humanize_age(mtime):
    if mtime == 0:
        return "never"
    age = time.time() - mtime
    if age < 60:
        return f"{int(age)}s ago"
    if age < 3600:
        return f"{int(age/60)}m ago"
    if age < 86400:
        return f"{int(age/3600)}h ago"
    return f"{int(age/86400)}d ago"


def find_qt_lib_dir():
    matches = glob(str(WFINFO_DIR / ".venv/lib*/python*/site-packages/PySide6/Qt/lib"))
    return matches[0] if matches else None


class ControlPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WFInfo Control Panel")
        self.resize(720, 720)

        self.process = None
        self._step_timeout_process = None

        self.setMinimumSize(700, 600)
        self._wfi_settings = QSettings("kiedas-orbiter", "ControlPanel")
        saved_geom = self._wfi_settings.value("geometry")
        if saved_geom:
            self.restoreGeometry(saved_geom)
        else:
            self.resize(950, 1050)
        _outer = QVBoxLayout(self)
        _outer.setContentsMargins(0, 0, 0, 0)
        _scroll = QScrollArea()
        _scroll.setWidgetResizable(True)
        _scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        _content = QWidget()
        _scroll.setWidget(_content)
        _outer.addWidget(_scroll)
        main = QVBoxLayout(_content)

        # Status
        status_group = QGroupBox("Status")
        form = QFormLayout()
        self.lbl_warframe = QLabel()
        self.lbl_wfinfo = QLabel()
        self.lbl_overlay = QLabel()
        self.lbl_refresh = QLabel()
        self.lbl_count = QLabel()
        self.lbl_detection = QLabel()
        form.addRow("Warframe:", self.lbl_warframe)
        form.addRow("orbiter:", self.lbl_wfinfo)
        form.addRow("Overlay:", self.lbl_overlay)
        form.addRow("Last inventory refresh:", self.lbl_refresh)
        form.addRow("Owned items in db:", self.lbl_count)
        form.addRow("Last detection:", self.lbl_detection)
        status_group.setLayout(form)
        main.addWidget(status_group)

        # Primary action
        self.btn_refresh = QPushButton("Refresh Inventory from Warframe")
        self.btn_refresh.setStyleSheet(
            f"QPushButton {{ font-size: 14pt; padding: 16px; "
            f"background-color: {BG_CARD}; color: {GOLD}; border: 1px solid {GOLD}; border-radius: 5px; font-weight: 700; }}"
            f"QPushButton:hover {{ background-color: {BG_PANEL}; color: {GOLD_BRIGHT}; border-color: {GOLD_BRIGHT}; }}"
            f"QPushButton:disabled {{ background-color: {BG_INPUT}; color: {FG_DIM}; border-color: {BORDER}; }}"
        )
        self.btn_refresh.clicked.connect(self.refresh_inventory)
        main.addWidget(self.btn_refresh)

        warning = QLabel(
            "Runs warframe-api-helper to re-read your inventory from Warframe's "
            "memory and rebuilds derived data. Requires Warframe running — "
            "best done in your orbiter or on a loading screen."
        )
        warning.setStyleSheet(f"color: {GOLD_BRIGHT}; padding: 4px;")
        warning.setWordWrap(True)
        main.addWidget(warning)

        # Maintenance
        maint = QGroupBox("Maintenance")
        grid = QGridLayout()

        self.btn_update = QPushButton("Update Warframe Data")
        self.btn_update.setToolTip("Refreshes prices and item list (./update.sh)")
        self.btn_update.clicked.connect(self.update_data)
        grid.addWidget(self.btn_update, 0, 0)

        self.btn_reset_cache = QPushButton("Reset WFCD Cache")
        self.btn_reset_cache.setToolTip("Deletes wfcd_all_cache.json so it re-downloads")
        self.btn_reset_cache.clicked.connect(self.reset_wfcd_cache)
        grid.addWidget(self.btn_reset_cache, 0, 1)

        self.btn_rebuild = QPushButton("Rebuild Helper")
        self.btn_rebuild.setToolTip("Pulls + rebuilds warframe-api-helper")
        self.btn_rebuild.clicked.connect(self.rebuild_helper)
        grid.addWidget(self.btn_rebuild, 1, 0)

        self.btn_overlay = QPushButton("Restart Overlay")
        self.btn_overlay.setToolTip("Kills and re-launches the overlay process")
        self.btn_overlay.clicked.connect(self.restart_overlay)
        grid.addWidget(self.btn_overlay, 1, 1)

        self.btn_test = QPushButton("Test Overlay (fake detection)")
        self.btn_test.setToolTip("Writes a fake state file so the overlay pops up")
        self.btn_test.clicked.connect(self.test_overlay)
        grid.addWidget(self.btn_test, 2, 0, 1, 2)

        self.btn_missing = QPushButton("Show Missing Parts...")
        self.btn_missing.setToolTip("Open the missing-parts tracker: NEED items + relics that drop them")
        self.btn_missing.clicked.connect(self.open_missing_parts)
        grid.addWidget(self.btn_missing, 3, 0, 1, 2)

        self.btn_reload_cfg = QPushButton("Reload Config")
        self.btn_reload_cfg.setToolTip("Restart wfinfo to pick up changes from config.json (trigger pattern, sleep durations, window name)")
        self.btn_reload_cfg.clicked.connect(self.reload_config)
        grid.addWidget(self.btn_reload_cfg, 4, 0, 1, 2)

        self.btn_refresh_wfcd = QPushButton("Refresh WFCD Cache")
        self.btn_refresh_wfcd.setToolTip("Pull fresh All.json from GitHub (bypasses api.warframestat.us). Safe to run anytime.")
        self.btn_refresh_wfcd.clicked.connect(self.refresh_wfcd_cache)
        grid.addWidget(self.btn_refresh_wfcd, 5, 0)

        self.btn_real_prices = QPushButton("Real Prices (slow, ~5min)")
        self.btn_real_prices.setToolTip("Fetch real plat prices from warframe.market for all prime parts. Takes several minutes due to rate limits. Cached for 24h.")
        self.btn_real_prices.clicked.connect(self.fetch_real_prices)
        grid.addWidget(self.btn_real_prices, 5, 1)

        maint.setLayout(grid)
        main.addWidget(maint)

        # Health dashboard - live status of every component
        self.health = HealthWidget()
        main.addWidget(self.health)

        # Log viewer - split: live overlay log + preserved command output
        log_group = QGroupBox("Live Overlay Log")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("monospace", 9))
        self.log_text.setStyleSheet(f"background-color: {BG_INPUT}; color: {FG}; border: 1px solid {BORDER}; border-radius: 4px;")
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        main.addWidget(log_group, stretch=1)

        cmd_group = QGroupBox("Command Output (preserved)")
        cmd_layout = QVBoxLayout()
        self.cmd_text = QTextEdit()
        self.cmd_text.setReadOnly(True)
        self.cmd_text.setFont(QFont("monospace", 9))
        self.cmd_text.setStyleSheet(f"background-color: {BG_INPUT}; color: {FG}; border: 1px solid {BORDER}; border-radius: 4px;")
        cmd_layout.addWidget(self.cmd_text)
        cmd_group.setLayout(cmd_layout)
        main.addWidget(cmd_group, stretch=1)

        self.lbl_status = QLabel("Idle")
        self.lbl_status.setStyleSheet(
            f"padding: 6px; background-color: {BG_PANEL}; color: {FG_DIM};"
        )
        main.addWidget(self.lbl_status)

        # Status refresh timer
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.update_status)
        self.refresh_timer.start(2000)
        self.update_status()

    # ---------- status updates ----------

    def update_status(self):
        wf = pgrep("Warframe.x64.exe")
        info = pgrep("target/release/orbiter")
        ov = pgrep("overlay.py")
        self.lbl_warframe.setText(self._status_html(wf))
        self.lbl_wfinfo.setText(self._status_html(info))
        self.lbl_overlay.setText(self._status_html(ov))

        if OWNED_FILE.exists():
            self.lbl_refresh.setText(humanize_age(OWNED_FILE.stat().st_mtime))
            try:
                owned = json.loads(OWNED_FILE.read_text())
                total = len(owned)
                need = sum(1 for v in owned.values()
                           if (isinstance(v, int) and v == 0)
                           or (isinstance(v, dict) and v.get("status") == "NEED"))
                self.lbl_count.setText(
                    f"{total} total ({need} NEED, {total - need} OWNED)"
                )
            except Exception:
                self.lbl_count.setText("(parse error)")
        else:
            self.lbl_refresh.setText("never")
            self.lbl_count.setText("(no file)")

        if STATE_FILE.exists():
            try:
                state = json.loads(STATE_FILE.read_text())
                rewards = state.get("rewards", [])
                names = [r.get("name", "?") for r in rewards[:4]]
                age = humanize_age(STATE_FILE.stat().st_mtime)
                short = " / ".join(n[:22] for n in names)
                self.lbl_detection.setText(f"{age}: {short}")
            except Exception:
                self.lbl_detection.setText(humanize_age(STATE_FILE.stat().st_mtime))
        else:
            self.lbl_detection.setText("(none yet)")

        # Tail the log only when no command is running
        running = self.process is not None and self.process.state() != QProcess.NotRunning
        if not running and LOG_FILE.exists():
            try:
                with open(LOG_FILE, "rb") as f:
                    f.seek(0, os.SEEK_END)
                    sz = f.tell()
                    f.seek(max(0, sz - 4000))
                    tail = f.read().decode("utf-8", errors="replace")
                lines = tail.splitlines()[-25:]
                new_text = "\n".join(lines)
                if new_text != self.log_text.toPlainText():
                    self.log_text.setPlainText(new_text)
                    sb = self.log_text.verticalScrollBar()
                    sb.setValue(sb.maximum())
            except OSError:
                pass

    def _status_html(self, running):
        if running:
            return '<span style="color: #4caf50; font-weight: bold;">Running</span>'
        return '<span style="color: #888;">Not running</span>'

    # ---------- command running ----------

    def _set_buttons_enabled(self, enabled):
        for b in [self.btn_refresh, self.btn_update, self.btn_reset_cache,
                  self.btn_rebuild, self.btn_overlay, self.btn_test, self.btn_missing]:
            b.setEnabled(enabled)

    def closeEvent(self, event):
        if hasattr(self, "_wfi_settings"):
            self._wfi_settings.setValue("geometry", self.saveGeometry())
        event.accept()

    def _run_command(self, steps, cwd, description, on_success=None, timeout_ms=60_000):
        """Run a sequence of commands, each an argv list (e.g. [py, 'script.py',
        'arg']) — no shell involved, so this works identically on Linux and
        Windows. Stops the sequence on the first non-zero exit, mirroring
        what bash '&&' chaining did in the old single-string version.
        on_success, if given, is called once after the whole chain exits 0.

        timeout_ms is a per-step force-kill timeout (see _check_step_timeout)
        - defaults to 60s for typically-fast steps, but pass a longer value
        for anything genuinely slow (e.g. warframe.market price fetching,
        which legitimately takes ~5 minutes) so it isn't mistaken for the
        same kind of hang and killed early."""
        if self.process and self.process.state() != QProcess.NotRunning:
            QMessageBox.warning(self, "Busy", "Another command is already running.")
            return
        self._pending_steps = [list(s) for s in steps]
        self._pending_cwd = cwd
        self._pending_on_success = on_success
        self._pending_timeout_ms = timeout_ms
        self._set_buttons_enabled(False)
        self.lbl_status.setText(f"Running: {description}")
        self.cmd_text.clear()
        self.cmd_text.append(f"=== {description} ===\n")
        self._run_next_step()

    def _run_next_step(self):
        if not self._pending_steps:
            self._process_finished(0, None)
            return
        argv = self._pending_steps.pop(0)
        self.cmd_text.append(f"$ {' '.join(str(a) for a in argv)}")

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._process_output)
        self.process.finished.connect(self._step_finished)
        self.process.errorOccurred.connect(self._process_error)
        self.process.setWorkingDirectory(str(self._pending_cwd))
        self.process.start(str(argv[0]), [str(a) for a in argv[1:]])

        # Some external tools (warframe-api-helper.exe in particular, seen
        # live on Windows) print their result but don't actually exit the
        # process afterward, which without this left the whole window stuck
        # on "Running:..." with every button disabled forever - QProcess
        # never emits 'finished' for a process that's still alive. Force-
        # kill anything that's still running after a generous timeout so a
        # single misbehaving step can't hang the app. Timeout is per-command
        # (see _run_command) so a legitimately slow step doesn't get killed
        # for taking as long as it's supposed to.
        self._step_timeout_process = self.process
        timeout_ms = getattr(self, "_pending_timeout_ms", 60_000)
        self._step_timeout_seconds = timeout_ms // 1000
        QTimer.singleShot(timeout_ms, self._check_step_timeout)

    def _check_step_timeout(self):
        proc = self._step_timeout_process
        if proc is None or proc is not self.process:
            return  # already finished/replaced - nothing to do
        if proc.state() != QProcess.NotRunning:
            self.cmd_text.append(
                f"\n=== Step timed out after {self._step_timeout_seconds}s, killing it and moving on ==="
            )
            proc.kill()

    def _step_finished(self, code, status):
        if code != 0:
            self._process_finished(code, status)
            return
        self._run_next_step()

    def _process_error(self, error):
        # Fires when a step's program fails to even start (bad path, not
        # executable, etc). Without this, QProcess never emits 'finished'
        # in that case and the UI hangs forever on "Running:..." with
        # every button disabled, since only 'finished' was handled before.
        if error == QProcess.FailedToStart:
            argv = self.process.program() if self.process else "?"
            self.cmd_text.append(f"\n=== Failed to start: {argv} ===")
            self.lbl_status.setText("Failed to start")
            self._set_buttons_enabled(True)
            self.process = None
            self._pending_steps = []

    def _process_output(self):
        if self.process:
            data = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
            self.cmd_text.append(data.rstrip())
            sb = self.cmd_text.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _process_finished(self, code, _status):
        self.cmd_text.append(f"\n=== Finished (exit code {code}) ===")
        self.lbl_status.setText(f"Done (exit {code})")
        self._set_buttons_enabled(True)
        self.process = None
        self.update_status()
        on_success = getattr(self, '_pending_on_success', None)
        self._pending_on_success = None
        if on_success and code == 0:
            on_success()

    # ---------- button handlers ----------

    def reload_config(self):
        if self.process and self.process.state() != QProcess.NotRunning:
            QMessageBox.warning(self, "Busy", "Another command is already running.")
            return
        self._set_buttons_enabled(False)
        self.lbl_status.setText("Running: Reload orbiter config")
        self.cmd_text.clear()
        self.cmd_text.append("=== Reload orbiter config ===\n")
        try:
            self.cmd_text.append("Current config:\n" + (WFINFO_DIR / "config.json").read_text())
        except OSError as e:
            self.cmd_text.append(f"(could not read config.json: {e})")
        self.cmd_text.append("\nRestarting orbiter...")

        killed = kill_processes("orbiter")
        self.cmd_text.append(f"Stopped {killed} running orbiter process(es).")
        # QTimer instead of time.sleep — this runs on the GUI thread, and a
        # real sleep() here would freeze the whole window for a few seconds.
        # 2s (not 1s) gives Windows more headroom to fully release the killed
        # process's global hotkey registration before the new one tries to
        # claim it - seen live: relaunching too soon after a kill can still
        # hit AlreadyRegistered even though the old process is already gone.
        QTimer.singleShot(2000, self._reload_config_launch)

    def _reload_config_launch(self):
        from platform_utils import launch_detached, clean_env_for_launch, IS_LINUX
        log_file = DATA_DIR / "orbiter.log"
        # orbiter.exe takes the EE.log path as a positional CLI argument -
        # without it, it falls back to its own built-in default guess and
        # silently ignores whatever the user configured (Save Paths) in
        # config.json. get_ee_log_path() already resolves override ->
        # auto-detect the same way the rest of the app does, so pass it
        # through explicitly instead of leaving the binary to guess on its
        # own with a narrower, less accurate fallback.
        ee_path = get_ee_log_path()
        log_path_arg = [str(ee_path)] if ee_path is not None else []
        try:
            if IS_LINUX:
                # launch-orbiter.sh handles Bazzite/gamescope-specific setup
                # (DISPLAY detection, host libs, portal bus) that Windows
                # simply doesn't need — there we can launch the exe directly.
                launch_detached(["./launch-orbiter.sh"] + log_path_arg, cwd=WFINFO_DIR,
                                 env=clean_env_for_launch(), log_file=log_file)
            else:
                launch_detached([str(WFINFO_DIR / "orbiter.exe")] + log_path_arg, cwd=WFINFO_DIR,
                                 log_file=log_file)
        except OSError as e:
            self.cmd_text.append(f"ERROR: failed to launch orbiter: {e}")
            self.lbl_status.setText("Failed")
            self._set_buttons_enabled(True)
            return
        QTimer.singleShot(2000, self._reload_config_report)

    def _reload_config_report(self):
        log_file = DATA_DIR / "orbiter.log"
        try:
            log_tail = log_file.read_text().splitlines()[-15:]
        except OSError:
            log_tail = ["(no log yet)"]
        self.cmd_text.append("orbiter restarted:\n" + "\n".join(log_tail))
        self.lbl_status.setText("Done")
        self._set_buttons_enabled(True)
        self.update_status()

    def refresh_inventory(self):
        # warframe-api-helper reads inventory directly from Warframe's own
        # memory/API — no third-party app needed. It tries a cached auth
        # token first and only needs Warframe actually running if that
        # token no longer works, so we don't gate the button on Warframe
        # being detected — that would block the legitimate cached-token
        # path. The helper prints its own clear message ("Process not
        # found.") in the command output if a live scan turns out to be
        # necessary and Warframe isn't open.
        from download_helper import API_HELPER_OUTPUT_PATH
        helper = API_HELPER_OUTPUT_PATH.get(sys.platform, WFINFO_DIR / "warframe-api-helper")
        if not helper.exists():
            QMessageBox.warning(
                self, "Helper not installed",
                "warframe-api-helper wasn't found. Run install.py again, or "
                "python download_helper.py, to fetch it."
            )
            return

        py = str(VENV_PYTHON)
        # populate_owned.py takes a literal path argument - it has no idea
        # about config.json's inventory_path override on its own, so this
        # has to resolve it explicitly. Without this, "Save Paths" appeared
        # to silently do nothing for inventory.json, because the saved
        # override genuinely was being written to config.json correctly,
        # it just wasn't being read by anything in this pipeline - the
        # literal string "inventory.json" (relative to WFINFO_DIR) was
        # used instead, every time, regardless of what was configured.
        inv_path = str(get_inventory_path())
        self._run_command(
            [
                # Best-effort: if the helper fails (no Warframe running, no
                # valid cached token - common on a machine where inventory.json
                # was just copied over from elsewhere rather than fetched
                # live), the existing inventory.json is still perfectly good
                # for the rest of this chain, so don't abort the whole
                # pipeline over it. Wrapped to always exit 0 regardless of
                # the helper's own result.
                [py, "-c", f"import subprocess; subprocess.run([{str(helper)!r}])"],
                [py, "populate_owned.py", inv_path, "owned_items.json"],
                [py, "populate_crafted.py"],
                [py, "populate_relics.py"],
                [py, "populate_equipment.py"],
                [py, "populate_images.py"],
            ],
            cwd=WFINFO_DIR,
            description="Refresh inventory from Warframe",
        )
        # kill_processes replaces "pkill -f missing-parts.py" — done here
        # rather than as a chained step since it's not something that
        # should abort the refresh if the viewer isn't even running.
        kill_processes("missing-parts.py")

    def refresh_wfcd_cache(self):
        self._run_command(
            [[str(VENV_PYTHON), "refresh_wfcd_cache.py", "--force"]],
            cwd=WFINFO_DIR, description="Refresh WFCD cache from GitHub")

    def fetch_real_prices(self):
        self._run_command(
            [[str(VENV_PYTHON), "enrich_prices_from_market.py"]],
            cwd=WFINFO_DIR, description="Fetch real prices from warframe.market",
            on_success=self.reload_config,
            timeout_ms=600_000,  # this one legitimately takes ~5 minutes
        )

    def update_data(self):
        self._run_command(
            [[str(VENV_PYTHON), "update_data.py"]],
            cwd=WFINFO_DIR, description="Update Warframe data (safe)")

    def reset_wfcd_cache(self):
        try:
            if WFCD_CACHE.exists():
                WFCD_CACHE.unlink()
                QMessageBox.information(
                    self, "Done",
                    "WFCD cache deleted. It will re-download on the next refresh."
                )
            else:
                QMessageBox.information(
                    self, "Already gone",
                    "WFCD cache file doesn't exist; nothing to delete."
                )
        except OSError as e:
            QMessageBox.critical(self, "Failed", f"Could not delete cache: {e}")

    def rebuild_helper(self):
        if not HELPER_SRC.exists():
            QMessageBox.information(
                self, "Not needed for normal use",
                "This rebuilds warframe-api-helper from source — only useful "
                "if you're developing it yourself.\n\n"
                f"It expects a separate git clone at {HELPER_SRC}, which "
                "isn't part of the normal install (install.py downloads a "
                "pre-built binary instead, which is all you need).\n\n"
                "If you do want to build from source, clone "
                "https://github.com/glowseeker/warframe-api-helper there first."
            )
            return
        # Source-build tooling — genuinely Linux/bash-only (git, a Rust
        # toolchain, build.sh), unlike the rest of _run_command's steps.
        self._run_command(
            [["/bin/bash", "-c", f"git pull && ./build.sh && cp warframe-api-helper {WFINFO_DIR}/"]],
            cwd=HELPER_SRC,
            description="Rebuild helper",
        )

    def restart_overlay(self):
        kill_processes("overlay.py")
        time.sleep(0.5)
        qt_lib = find_qt_lib_dir()
        if not qt_lib:
            QMessageBox.critical(self, "Error", "Could not find PySide6 Qt lib directory.")
            return
        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = qt_lib + ":" + env.get("LD_LIBRARY_PATH", "")
        env["QT_QPA_PLATFORM"] = "xcb"
        subprocess.Popen(
            [str(VENV_PYTHON), str(OVERLAY_SCRIPT)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self.lbl_status.setText("Overlay restarted.")
        self.update_status()

    def test_overlay(self):
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        warframe = {"x": 1920, "y": 0, "width": 2560, "height": 1440}
        if STATE_FILE.exists():
            try:
                old = json.loads(STATE_FILE.read_text())
                if old.get("warframe"):
                    warframe = old["warframe"]
            except Exception:
                pass
        state = {
            "timestamp": int(time.time()),
            "warframe": warframe,
            "rewards": [
                {"name": "Octavia Prime Systems Blueprint", "status": "OWNED", "count": 1},
                {"name": "Tenora Prime Blueprint", "status": "OWNED", "count": 3},
                {"name": "Harrow Prime Systems Blueprint", "status": "NEED", "count": 0},
                {"name": "Forma Blueprint", "status": "OWNED", "count": 12},
            ],
        }
        STATE_FILE.write_text(json.dumps(state))
        self.lbl_status.setText("Wrote fake state. Overlay should pop up.")


    def open_missing_parts(self):
        script = WFINFO_DIR / "missing-parts.py"
        if not script.exists():
            QMessageBox.critical(self, "Missing", f"{script} not found.")
            return
        qt_lib = find_qt_lib_dir()
        env = os.environ.copy()
        if qt_lib:
            env["LD_LIBRARY_PATH"] = qt_lib + ":" + env.get("LD_LIBRARY_PATH", "")
        env["QT_QPA_PLATFORM"] = "xcb"
        subprocess.Popen(
            [str(VENV_PYTHON), str(script)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )



def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(WFINFO_ICON))
    app.setStyleSheet(WFINFO_STYLESHEET)
    panel = ControlPanel()
    panel.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()