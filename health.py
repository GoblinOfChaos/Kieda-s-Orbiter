"""
health.py - Live health dashboard for the wfinfo stack.
Shows status of every component at a glance so when something breaks after a
Warframe update, you can see WHICH piece broke without cracking 5 test relics.
"""
import json
import re
import subprocess
import time
from pathlib import Path
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QGroupBox, QGridLayout, QLabel, QPushButton, QHBoxLayout

from paths import DATA_DIR
WFINFO_DIR = Path.home() / "wfinfo-ng"
LOG_DIR    = DATA_DIR
INVENTORY  = WFINFO_DIR / "inventory.json"
WFINFO_BIN = WFINFO_DIR / "target/release/orbiter"
WFINFO_SRC = WFINFO_DIR / "src/bin/main.rs"
STATE_FILE = DATA_DIR / "latest-detection.json"
def _get_ee_log():
    try:
        from paths import get_ee_log_path
        return get_ee_log_path()
    except Exception:
        return Path.home() / ".local/share/Steam/steamapps/compatdata/230410/pfx/drive_c/users/steamuser/AppData/Local/Warframe/EE.log"
EE_LOG = _get_ee_log()

from theme import COLOR_GREAT as GREEN, COLOR_GOOD as YELLOW, COLOR_BAD as RED, FG_DIM
GREY = FG_DIM


def pgrep_first(pattern):
    try:
        r = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True, timeout=2)
        if r.returncode == 0 and r.stdout.strip():
            return int(r.stdout.strip().split()[0])
    except Exception:
        pass
    return None

def proc_elapsed(pid):
    if pid is None:
        return None
    try:
        r = subprocess.run(["ps", "-o", "etime=", "-p", str(pid)],
                           capture_output=True, text=True, timeout=2)
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return None

def file_age(path):
    if not path.exists():
        return None
    return time.time() - path.stat().st_mtime

def fmt_age(secs):
    if secs is None:
        return "never"
    if secs < 60:    return f"{int(secs)}s ago"
    if secs < 3600:  return f"{int(secs/60)}m ago"
    if secs < 86400: return f"{int(secs/3600)}h {int((secs%3600)/60)}m ago"
    days = secs / 86400
    return f"{days:.1f} days ago"


class HealthWidget(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("● Health", parent)
        layout = QGridLayout(self)
        layout.setColumnStretch(1, 1)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(3)

        self.rows = {}
        spec = [
            ("orbiter",   "orbiter (capture/OCR)"),
            ("overlay",  "Overlay (display)"),
            ("watcher",  "Watcher (auto-restart)"),
            ("warframe", "Warframe (game)"),
            ("ocr",      "Last OCR result"),
            ("trigger",  "EE.log trigger"),
            ("helper",   "Inventory refresh"),
            ("data",     "Data files"),
        ]
        for i, (key, label) in enumerate(spec):
            name = QLabel(label + ":")
            name.setStyleSheet(f"color: {GREY};")
            name.setAlignment(Qt.AlignTop | Qt.AlignRight)
            value = QLabel("checking…")
            value.setTextFormat(Qt.RichText)
            value.setWordWrap(True)
            layout.addWidget(name, i, 0, Qt.AlignTop)
            layout.addWidget(value, i, 1)
            self.rows[key] = value

        bar = QHBoxLayout()
        bar.addStretch()
        btn = QPushButton("Refresh now")
        btn.setMaximumWidth(120)
        btn.clicked.connect(self.refresh)
        bar.addWidget(btn)
        layout.addLayout(bar, len(spec), 0, 1, 2)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(5000)
        self.refresh()

    def _c(self, text, color):
        return f'<span style="color: {color};">{text}</span>'

    def refresh(self):
        # Process status rows
        for key, pattern, friendly in [
            ("orbiter",   "target/release/orbiter", "orbiter"),
            ("overlay",  "wfinfo-ng/overlay.py",  "overlay"),
            ("watcher",  "warframe-watcher.py",   "watcher"),
            ("warframe", "Warframe.x64.exe",      "Warframe"),
        ]:
            pid = pgrep_first(pattern)
            if pid:
                et = proc_elapsed(pid)
                extra = ""
                if key == "orbiter":
                    age = file_age(WFINFO_BIN)
                    extra = f", binary {fmt_age(age)}"
                self.rows[key].setText(self._c(f'✓ running ({et}){extra}', GREEN))
            else:
                if key == "warframe":
                    self.rows[key].setText(self._c('○ not running (waiting for game)', GREY))
                elif key == "watcher":
                    self.rows[key].setText(self._c('⚠ NOT running (Warframe restarts won\'t be detected)', YELLOW))
                else:
                    self.rows[key].setText(self._c('✗ NOT running', RED))

        # Last OCR result (from state file)
        if not STATE_FILE.exists():
            self.rows["ocr"].setText(self._c("? no capture yet", GREY))
        else:
            try:
                data = json.loads(STATE_FILE.read_text())
                rewards = data.get("rewards", [])
                ts = data.get("timestamp", 0)
                age = time.time() - ts if ts else None
                n_unknown = sum(1 for r in rewards if r.get("status") == "UNKNOWN")
                n_known = len(rewards) - n_unknown
                if len(rewards) == 0:
                    msg, color = "? empty (no items)", YELLOW
                elif n_unknown == 0:
                    msg = f'✓ {n_known} items, all resolved ({fmt_age(age)})'
                    color = GREEN
                elif n_known > 0:
                    msg = f'⚠ {n_known} resolved, {n_unknown} UNKNOWN ({fmt_age(age)})'
                    color = YELLOW
                else:
                    msg = f'✗ all {n_unknown} UNKNOWN ({fmt_age(age)})'
                    color = RED
                self.rows["ocr"].setText(self._c(msg, color))
            except Exception as e:
                self.rows["ocr"].setText(self._c(f"? error: {e}", GREY))

        # Trigger pattern check
        self._update_trigger()

        # Inventory age
        age = file_age(INVENTORY)
        if age is None:
            self.rows["helper"].setText(self._c("✗ inventory.json missing", RED))
        else:
            days = age / 86400
            if days < 1: color = GREEN; icon = "✓"
            elif days < 3: color = YELLOW; icon = "⚠"
            else: color = RED; icon = "✗"
            self.rows["helper"].setText(self._c(f'{icon} last refresh: {fmt_age(age)}', color))

        # Data files
        rows = []
        for label, path in [
            ("owned_items",     WFINFO_DIR / "owned_items.json"),
            ("owned_relics",    WFINFO_DIR / "owned_relics.json"),
            ("crafted_parts",   LOG_DIR / "crafted_parts.json"),
            ("equipment_status",LOG_DIR / "equipment_status.json"),
        ]:
            age = file_age(path)
            if age is None: c = RED; t = "missing"
            elif age < 86400: c = GREEN; t = fmt_age(age)
            elif age < 86400 * 3: c = YELLOW; t = fmt_age(age)
            else: c = RED; t = fmt_age(age)
            rows.append(self._c(f"{label}: {t}", c))
        self.rows["data"].setText("<br/>".join(rows))

    def _update_trigger(self):
        # Read current trigger pattern out of main.rs
        pattern = None
        try:
            src = WFINFO_SRC.read_text()
            m = re.search(r'"(ProjectionRewardChoice\.lua:\s*[^"]+)"', src)
            if m:
                pattern = m.group(1)
        except Exception:
            pass

        if not pattern:
            self.rows["trigger"].setText(self._c("? couldn't read pattern from main.rs", GREY))
            return

        if not EE_LOG.exists():
            self.rows["trigger"].setText(self._c(f"⚠ '{pattern}'<br/>&nbsp;&nbsp;EE.log not found", YELLOW))
            return

        try:
            with open(EE_LOG, "rb") as f:
                f.seek(0, 2)
                sz = f.tell()
                f.seek(max(0, sz - 500_000))
                tail = f.read().decode("utf-8", errors="replace")
            count = tail.count(pattern)
            if count > 0:
                self.rows["trigger"].setText(
                    self._c(f'✓ "{pattern}"<br/>&nbsp;&nbsp;{count} hits in recent EE.log', GREEN))
            else:
                self.rows["trigger"].setText(
                    self._c(f'⚠ "{pattern}"<br/>&nbsp;&nbsp;0 hits in recent EE.log — Warframe may have renamed it', YELLOW))
        except Exception as e:
            self.rows["trigger"].setText(self._c(f"? error: {e}", GREY))
