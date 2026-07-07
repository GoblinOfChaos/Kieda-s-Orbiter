#!/usr/bin/env python3
"""
wfinfo pop-up overlay (PySide6, KDE-friendly window flags).
"""

import json
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
)
from paths import DATA_DIR

WFINFO_ICON = str(Path.home() / ".local/share/icons/hicolor/scalable/apps/orbiter.svg")

STATE_FILE = DATA_DIR / "latest-detection.json"
POSITION_FILE = DATA_DIR / "overlay-position.json"
CRAFTED_PARTS_FILE = DATA_DIR / "crafted_parts.json"
CONFIG_FILE = Path.home() / "wfinfo-ng/config.json"

RELIC_RECOMMEND_STATE_FILE = DATA_DIR / "relic-recommend.json"
RELIC_RECOMMEND_POSITION_FILE = DATA_DIR / "relic-recommend-position.json"


def _load_config():
    try:
        return json.loads(CONFIG_FILE.read_text())
    except Exception:
        return {}


_cfg = _load_config()
DISPLAY_DURATION_MS = int(_cfg.get("display_duration_ms") or 30000)
POLL_INTERVAL_MS = int(_cfg.get("poll_interval_ms") or 250)
# Safety-net auto-hide for the relic recommendation overlay, in case you back
# out of the relic-selection screen without confirming a pick (no EE.log line
# reliably marks that case, so the normal "confirmed a pick" trigger never fires).
RELIC_RECOMMEND_TIMEOUT_MS = 60000

BG = "#0b1628"  # Porsche sapphire — matches app background
TEXT = "#dce8f8"
OWNED = "#6a88aa"        # steel-blue-grey: already owned, deprioritize
CRAFTED = "#e8c96a"      # bright gold: collection-done
NEED = "#3eff3e"         # green: never had it, take this one
UNKNOWN_COLOR = "#ff5555" # red: OCR couldn't resolve the reward text

# Warframe doesn't log which fissure tier you're browsing until after you've
# already confirmed a relic (too late to filter), so instead each era gets its
# own color to make it easy to eyeball just the one matching your fissure.
ERA_COLORS = {
    "Lith": "#8fd3ff",
    "Meso": "#7fffb0",
    "Neo": "#ffb37f",
    "Axi": "#ff8fa3",
    "Vanguard": "#d0a3ff",
}


def log(msg):
    print(f"[overlay] {msg}", file=sys.stderr, flush=True)


def _target_screen(warframe_geom=None):
    """Return the QScreen the overlay should default to.

    Priority:
      1. config.json overlay_monitor = <index>  → that screen
      2. config.json overlay_monitor = "auto"   → screen containing Warframe window
      3. fallback                               → primary screen
    """
    from PySide6.QtWidgets import QApplication
    screens = QApplication.screens()
    if not screens:
        return None

    cfg = _load_config()
    monitor = cfg.get("overlay_monitor", "auto")

    if monitor != "auto":
        try:
            idx = int(monitor)
            if 0 <= idx < len(screens):
                return screens[idx]
        except (TypeError, ValueError):
            pass

    # Auto: find the screen that contains the Warframe window
    if warframe_geom:
        wx = warframe_geom.get("x", 0) + warframe_geom.get("width", 0) // 2
        wy = warframe_geom.get("y", 0) + warframe_geom.get("height", 0) // 2
        for s in screens:
            if s.geometry().contains(wx, wy):
                return s

    return QApplication.primaryScreen()


class _DraggableOverlay(QWidget):
    """Frameless, always-on-top, click-and-drag window whose position is
    remembered in `position_file` across drags and app restarts."""

    def __init__(self, position_file):
        super().__init__()
        self._position_file = position_file
        # Frameless, always-on-top, never steals focus.
        # On native Wayland (gamescope/KDE), Qt.SplashScreen is the only window
        # type that reliably maps to a surface role that does not trigger a focus
        # transfer. Qt.Tool can still steal focus because xdg_toplevel (which Qt.Tool
        # maps to on Wayland) sends an activation token that KDE honours.
        # Qt.SplashScreen maps to a non-interactive surface role.
        self.setWindowFlags(
            Qt.SplashScreen
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_X11DoNotAcceptFocus, True)
        self.setWindowOpacity(0.94)
        self.setStyleSheet(f"background-color: {BG};")
        self.setCursor(Qt.SizeAllCursor)
        self._drag_offset = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            if hasattr(self, "hide_timer"):
                self.hide_timer.stop()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._drag_offset is not None:
            self._save_position()
            self._drag_offset = None
            if hasattr(self, "hide_timer"):
                self.hide_timer.start(DISPLAY_DURATION_MS)
            event.accept()

    def _save_position(self):
        try:
            self._position_file.parent.mkdir(parents=True, exist_ok=True)
            self._position_file.write_text(json.dumps({"x": self.x(), "y": self.y()}))
            log(f"saved position ({self.x()}, {self.y()})")
        except OSError as e:
            log(f"could not save position: {e}")

    def _load_position(self):
        if not self._position_file.exists():
            return None
        try:
            data = json.loads(self._position_file.read_text())
            if "x" in data and "y" in data:
                return data
        except (OSError, json.JSONDecodeError):
            pass
        return None

    def _position_on_any_screen(self, x, y):
        for screen in QApplication.screens():
            g = screen.geometry()
            if g.x() <= x <= g.x() + g.width() and g.y() <= y <= g.y() + g.height():
                return True
        return False


class Overlay(_DraggableOverlay):
    def __init__(self):
        super().__init__(POSITION_FILE)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(12)

        self.reward_widgets = []
        for _ in range(4):
            col_widget = QWidget()
            col = QVBoxLayout(col_widget)
            col.setContentsMargins(8, 0, 8, 0)
            col.setSpacing(4)

            name_lbl = QLabel("")
            name_lbl.setAlignment(Qt.AlignCenter)
            name_lbl.setWordWrap(True)
            name_lbl.setStyleSheet(f"color: {TEXT}; font-size: 12px;")
            name_lbl.setMaximumWidth(220)
            col.addWidget(name_lbl)

            status_lbl = QLabel("")
            status_lbl.setAlignment(Qt.AlignCenter)
            col.addWidget(status_lbl)

            layout.addWidget(col_widget)
            self.reward_widgets.append((name_lbl, status_lbl))

        self.hide()

        self.last_timestamp = None
        self._last_warframe_geom = None
        self.crafted_parts = self._load_crafted_parts()
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll)
        self.poll_timer.start(POLL_INTERVAL_MS)
        log(f"started, polling {STATE_FILE}")

    def poll(self):
        self.poll_count = getattr(self, "poll_count", 0) + 1
        if self.poll_count % 8 == 0:  # ~2s
            log(f"poll #{self.poll_count} state_file_exists={STATE_FILE.exists()}")
        try:
            if STATE_FILE.exists():
                with open(STATE_FILE, "r") as f:
                    state = json.load(f)
                ts = state.get("timestamp")
                if ts != self.last_timestamp:
                    log(f"new detection, timestamp={ts}")
                    self.last_timestamp = ts
                    self._last_warframe_geom = state.get("warframe")
                    self.crafted_parts = self._load_crafted_parts()
                    self.show_rewards(state.get("rewards", []))
        except (OSError, json.JSONDecodeError) as e:
            log(f"poll error: {e}")

    def show_rewards(self, rewards):
        # Pad to 4 only if we have rewards; for solo (3) or duos (2) show exactly that many
        # Hide unused reward columns rather than showing empty/unknown slots
        count = max(len(rewards), 1)
        rewards = rewards[:4]
        for i, (name_lbl, status_lbl) in enumerate(self.reward_widgets):
            visible = i < len(rewards)
            name_lbl.parentWidget().setVisible(visible)
        if not rewards:
            return

        for (name_lbl, status_lbl), r in zip(self.reward_widgets, rewards):
            name = r.get("name", "")
            name_lbl.setText(name)
            status = r.get("status", "UNKNOWN")
            count = r.get("count", 0)
            # Promote NEED to CRAFTED when this part is in the crafted set
            if status == "NEED" and self._is_crafted(name):
                status = "CRAFTED"
            if status == "OWNED":
                status_lbl.setText(f"OWNED x{count}")
                color = OWNED
            elif status == "CRAFTED":
                status_lbl.setText("CRAFTED")
                color = CRAFTED
            elif status == "NEED":
                status_lbl.setText("NEED")
                color = NEED
            else:
                status_lbl.setText("UNKNOWN")
                color = UNKNOWN_COLOR
            status_lbl.setStyleSheet(
                f"color: {color}; font-size: 18px; font-weight: bold;"
            )

        self.adjustSize()
        saved = self._load_position()
        if saved and self._position_on_any_screen(saved["x"], saved["y"]):
            x, y = saved["x"], saved["y"]
            self.move(x, y)
        else:
            screen = _target_screen(self._last_warframe_geom)
            if screen is None:
                screen = QApplication.primaryScreen()
            g = screen.geometry()
            x = g.x() + (g.width() - self.width()) // 2
            y = g.y() + g.height() - self.height() - 80
            self.move(x, y)
        self.show()
        log(f"shown at ({x},{y}) size {self.width()}x{self.height()}, visible={self.isVisible()}")
        self.hide_timer.start(DISPLAY_DURATION_MS)


    def _load_crafted_parts(self):
        """Set of parts you've crafted-before (own the Prime, or mastered it)."""
        try:
            return set(json.loads(CRAFTED_PARTS_FILE.read_text()))
        except (OSError, json.JSONDecodeError):
            return set()

    def _is_crafted(self, name):
        """OCR returns names like 'Rhino Prime Systems Blueprint' but
        crafted_parts.json stores them without the ' Blueprint' suffix for
        warframe component parts. Match both forms."""
        if name in self.crafted_parts:
            return True
        if name.endswith(" Blueprint"):
            if name[: -len(" Blueprint")] in self.crafted_parts:
                return True
        else:
            if (name + " Blueprint") in self.crafted_parts:
                return True
        return False

class RelicRecommendOverlay(_DraggableOverlay):
    """Shows a ranked list of your OWNED relics (by expected plat value for
    your NEED list) when the relic-selection screen opens at Navigation,
    before a Void Fissure mission. Hides again once you confirm a pick."""

    def __init__(self):
        super().__init__(RELIC_RECOMMEND_POSITION_FILE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        title = QLabel("Relics ranked by your NEED list")
        title.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: bold;")
        layout.addWidget(title)

        self.rows = []
        for _ in range(8):
            row_lbl = QLabel("")
            row_lbl.setStyleSheet(f"color: {TEXT}; font-size: 13px;")
            layout.addWidget(row_lbl)
            self.rows.append(row_lbl)

        self.hide()
        self.last_timestamp = None
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll)
        self.poll_timer.start(POLL_INTERVAL_MS)
        log(f"relic-recommend overlay started, polling {RELIC_RECOMMEND_STATE_FILE}")

    def poll(self):
        try:
            if RELIC_RECOMMEND_STATE_FILE.exists():
                with open(RELIC_RECOMMEND_STATE_FILE, "r") as f:
                    state = json.load(f)
                ts = state.get("timestamp")
                if ts != self.last_timestamp:
                    self.last_timestamp = ts
                    if state.get("visible"):
                        self.show_relics(state.get("relics", []))
                    else:
                        self.hide()
        except (OSError, json.JSONDecodeError) as e:
            log(f"relic-recommend poll error: {e}")

    def show_relics(self, relics):
        if not relics:
            self.hide()
            return
        for i, row_lbl in enumerate(self.rows):
            if i < len(relics):
                r = relics[i]
                era_color = ERA_COLORS.get(r['era'], TEXT)
                row_lbl.setTextFormat(Qt.RichText)
                row_lbl.setText(
                    f"<span style='color:{era_color}; font-weight:bold;'>{r['era']} {r['name']}</span>"
                    f"  —  NEED: {r['ev_need']:.1f}p"
                    f"  (total {r['ev_total']:.1f}p, owned x{r['owned']})"
                )
                row_lbl.setVisible(True)
            else:
                row_lbl.setVisible(False)

        self.adjustSize()
        saved = self._load_position()
        if saved and self._position_on_any_screen(saved["x"], saved["y"]):
            x, y = saved["x"], saved["y"]
        else:
            screen = QApplication.primaryScreen().geometry()
            x = screen.x() + 40
            y = screen.y() + 80
        self.move(x, y)
        self.show()
        self.hide_timer.start(RELIC_RECOMMEND_TIMEOUT_MS)
        log(f"relic-recommend shown at ({x},{y}) with {len(relics)} relics")


def main():
    import os, signal, fcntl

    # ── Singleton: kill any other overlay.py before starting ─────────────
    pid_path = DATA_DIR / "overlay.pid"
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    # Kill previous instance if still running
    try:
        old_pid = int(pid_path.read_text().strip())
        if old_pid != os.getpid():
            try:
                os.kill(old_pid, signal.SIGTERM)
                log(f"killed previous overlay instance (pid {old_pid})")
                import time as _t; _t.sleep(0.3)
            except ProcessLookupError:
                pass  # already dead
    except Exception:
        pass
    pid_path.write_text(str(os.getpid()))

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(WFINFO_ICON))
    overlay = Overlay()  # keep reference alive
    relic_overlay = RelicRecommendOverlay()  # keep reference alive
    sys.exit(app.exec())


if __name__ == "__main__":
    main()