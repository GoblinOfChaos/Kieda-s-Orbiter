#!/usr/bin/env python3
"""
riven_grader_overlay.py - always-on-top overlay showing your graded rivens.

Watches " + str(DATA_DIR) + "/riven-graded.json (written by riven_grader_watcher.py
whenever inventory.json changes) and shows a floating window with all your
rivens ranked by roll quality.  Updates automatically — no interaction needed.

The window is always visible while Warframe is running so you can glance at it
while rerolling at the Arsenal.  It hides itself 120 seconds after the last
inventory refresh (so it fades away when you leave the Arsenal), then reappears
the next time inventory is refreshed.
"""

import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame,
)
from paths import DATA_DIR, WFINFO_DIR


def _running_under_gamescope() -> bool:
    """gamescope (Steam's nested Wayland compositor for the game) sets this
    env var on everything it launches. On a normal desktop compositor
    (regular KDE/GNOME Wayland or X11), this won't be set."""
    return bool(os.environ.get("GAMESCOPE_WAYLAND_DISPLAY"))


STATE_FILE = DATA_DIR / "riven-graded.json"
PREV_STATE_FILE = DATA_DIR / "riven-graded-prev.json"
POSITION_FILE = DATA_DIR / "riven-overlay-position.json"
WFINFO_ICON = str(WFINFO_DIR / "orbiter.svg")

POLL_INTERVAL_MS = 1000
AUTO_HIDE_MS = 120_000   # hide 2 min after last update if not rerolling

BG = "#0b1628"
TEXT = "#dce8f8"
DIM = "#6a88aa"
GREAT_COLOR = "#3eff3e"
GOOD_COLOR = "#ffd24c"
OK_COLOR = "#ff9933"
WEAK_COLOR = "#ff6060"
REROLL_COLOR = "#ff4444"
UNKNOWN_COLOR = "#6a88aa"

GRADE_COLORS = {
    "great": GREAT_COLOR,
    "good": GOOD_COLOR,
    "ok": OK_COLOR,
    "weak": WEAK_COLOR,
    "reroll": REROLL_COLOR,
    "unknown": UNKNOWN_COLOR,
}


CONFIG_FILE = WFINFO_DIR / "config.json"


def _load_config():
    try:
        return json.loads(CONFIG_FILE.read_text())
    except Exception:
        return {}


def _target_screen():
    """Return the QScreen for the overlay based on config overlay_monitor setting."""
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
    return QApplication.primaryScreen()


def _save_position(x, y):
    try:
        POSITION_FILE.parent.mkdir(parents=True, exist_ok=True)
        POSITION_FILE.write_text(json.dumps({"x": x, "y": y}))
    except OSError:
        pass


def _load_position():
    try:
        d = json.loads(POSITION_FILE.read_text())
        if "x" in d and "y" in d:
            return d
    except Exception:
        pass
    return None


class RivenGraderOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self._last_ts = None
        self._drag_offset = None

        flags = (
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        if _running_under_gamescope():
            # Only needed to stop gamescope from releasing its input grab on
            # the game — on a normal desktop WM it removes the WM from
            # positioning/sizing/input entirely, breaking drag-to-move.
            flags |= Qt.X11BypassWindowManagerHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_X11DoNotAcceptFocus, True)
        self.setWindowOpacity(0.95)
        self.setStyleSheet(f"background-color: {BG}; color: {TEXT};")
        self.setMinimumWidth(380)
        self.setMaximumWidth(520)

        self._setup_ui()
        self._restore_position()

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._poll)
        self.poll_timer.start(POLL_INTERVAL_MS)

        print("[riven-overlay] started, polling", STATE_FILE, file=sys.stderr)

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Title bar
        title_bar = QFrame()
        title_bar.setStyleSheet(f"background: #0f1e3d; border-bottom: 1px solid #2e6db4; padding: 4px 10px;")
        title_row = QHBoxLayout(title_bar)
        title_row.setContentsMargins(8, 4, 8, 4)
        title_lbl = QLabel("⚔ Riven Rolls")
        title_lbl.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: bold;")
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        self._age_lbl = QLabel("")
        self._age_lbl.setStyleSheet(f"color: {DIM}; font-size: 10px;")
        title_row.addWidget(self._age_lbl)
        close_btn = QLabel("  ✕")
        close_btn.setStyleSheet(f"color: {DIM}; font-size: 12px;")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.mousePressEvent = lambda e: self.hide()
        title_row.addWidget(close_btn)
        outer.addWidget(title_bar)

        # Scrollable riven list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"background: {BG}; border: none;")
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(8, 6, 8, 6)
        self._content_layout.setSpacing(4)
        scroll.setWidget(self._content)
        scroll.setMaximumHeight(480)
        outer.addWidget(scroll)

        self._empty_lbl = QLabel("Waiting for inventory refresh…")
        self._empty_lbl.setAlignment(Qt.AlignCenter)
        self._empty_lbl.setStyleSheet(f"color: {DIM}; font-size: 11px; padding: 12px;")
        self._content_layout.addWidget(self._empty_lbl)

    def _clear_content(self):
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _poll(self):
        try:
            if not STATE_FILE.exists():
                return
            state = json.loads(STATE_FILE.read_text())
            ts = state.get("ts")
            if ts == self._last_ts:
                return
            self._last_ts = ts
            # Load previous state to detect rerolls (same ID, different stats)
            prev_by_id = {}
            if PREV_STATE_FILE.exists():
                try:
                    prev = json.loads(PREV_STATE_FILE.read_text())
                    prev_by_id = {r["id"]: r for r in prev.get("rivens", []) if r.get("id")}
                except Exception:
                    pass
            self._show_rivens(state.get("rivens", []), ts, prev_by_id)
        except Exception as e:
            print(f"[riven-overlay] poll error: {e}", file=sys.stderr)

    def _show_rivens(self, rivens, ts, prev_by_id=None):
        import time
        self._clear_content()
        prev_by_id = prev_by_id or {}

        if not rivens:
            lbl = QLabel("No rivens found in inventory")
            lbl.setStyleSheet(f"color: {DIM}; font-size: 11px;")
            lbl.setAlignment(Qt.AlignCenter)
            self._content_layout.addWidget(lbl)
        else:
            # Find which rivens changed (rerolled) — same id, different stats
            rerolled_ids = set()
            for r in rivens:
                rid = r.get("id")
                if rid and rid in prev_by_id:
                    prev = prev_by_id[rid]
                    if (prev.get("positives") != r.get("positives") or
                            prev.get("negatives") != r.get("negatives")):
                        rerolled_ids.add(rid)

            for r in rivens:
                prev = prev_by_id.get(r.get("id", ""))
                was_rerolled = r.get("id") in rerolled_ids
                self._content_layout.addWidget(
                    self._make_riven_row(r, prev if was_rerolled else None)
                )

        self._content_layout.addStretch()

        # Update age label
        age = int(time.time()) - ts
        self._age_lbl.setText(f"updated {age}s ago")

        # Position and show
        saved = _load_position()
        if saved and self._on_screen(saved["x"], saved["y"]):
            self.move(saved["x"], saved["y"])
        else:
            s = _target_screen() or QApplication.primaryScreen()
            g = s.geometry()
            self.move(g.x() + g.width() - 540, g.y() + 80)

        self.adjustSize()
        self.show()
        self.hide_timer.start(AUTO_HIDE_MS)
        print(f"[riven-overlay] showing {len(rivens)} rivens", file=sys.stderr)

    def _make_riven_row(self, r, prev=None):
        """Build a riven row widget. If prev is provided, show old vs new comparison."""
        frame = QFrame()
        grade = r.get("grade", "unknown")
        color = GRADE_COLORS.get(grade, UNKNOWN_COLOR)

        # Rerolled rivens get a highlighted border
        border_width = "4px" if prev else "3px"
        frame.setStyleSheet(
            f"background: #122040; border-left: {border_width} solid {color}; "
            f"border-radius: 3px; padding: 2px 6px;"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(1)

        # Top row: weapon name + grade label
        top = QHBoxLayout()
        weapon_lbl = QLabel(r.get("weapon", "?").title())
        weapon_lbl.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: bold;")
        top.addWidget(weapon_lbl)
        if prev:
            new_badge = QLabel(" ↻ REROLLED")
            new_badge.setStyleSheet(f"color: #ffd24c; font-size: 10px; font-weight: bold;")
            top.addWidget(new_badge)
        top.addStretch()
        grade_lbl = QLabel(r.get("label", ""))
        grade_lbl.setStyleSheet(f"color: {color}; font-size: 11px;")
        top.addWidget(grade_lbl)
        layout.addLayout(top)

        if prev:
            # Show OLD stats struck-through in dim color
            old_parts = prev.get("pos_display", []) + prev.get("neg_display", [])
            old_text = "  ·  ".join(old_parts) if old_parts else "No stats"
            old_grade = prev.get("grade", "unknown")
            old_color = GRADE_COLORS.get(old_grade, UNKNOWN_COLOR)
            old_lbl = QLabel(f"<s style='color:{old_color};'>OLD: {old_text}</s>")
            old_lbl.setTextFormat(Qt.RichText)
            old_lbl.setStyleSheet("font-size: 10px;")
            layout.addWidget(old_lbl)

        # NEW/current stats row
        stats_parts = r.get("pos_display", []) + r.get("neg_display", [])
        stats_text = "  ·  ".join(stats_parts) if stats_parts else "No stats"
        prefix = "NEW: " if prev else ""
        new_style = f"color: {color}; font-size: 10px; font-weight: bold;" if prev else f"color: #bdc3c7; font-size: 10px;"
        stats_lbl = QLabel(f"{prefix}{stats_text}")
        stats_lbl.setStyleSheet(new_style)
        layout.addWidget(stats_lbl)

        # Rerolls + polarity (small)
        meta_parts = []
        if r.get("rerolls", 0) > 0:
            meta_parts.append(f"{r['rerolls']} rerolls")
        if r.get("polarity"):
            meta_parts.append(r["polarity"])
        if meta_parts:
            meta_lbl = QLabel("  ".join(meta_parts))
            meta_lbl.setStyleSheet(f"color: {DIM}; font-size: 9px;")
            layout.addWidget(meta_lbl)

        return frame

    def _on_screen(self, x, y):
        for screen in QApplication.screens():
            g = screen.geometry()
            if g.x() <= x <= g.x() + g.width() and g.y() <= y <= g.y() + g.height():
                return True
        return False

    def _restore_position(self):
        saved = _load_position()
        if saved and self._on_screen(saved["x"], saved["y"]):
            self.move(saved["x"], saved["y"])
        else:
            s = _target_screen() or QApplication.primaryScreen()
            g = s.geometry()
            self.move(g.x() + g.width() - 540, g.y() + 80)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.hide_timer.stop()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._drag_offset is not None:
            _save_position(self.x(), self.y())
            self._drag_offset = None
            self.hide_timer.start(AUTO_HIDE_MS)
            event.accept()


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(WFINFO_ICON))
    w = RivenGraderOverlay()
    # Trigger an immediate poll so existing state shows on launch
    w._poll()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()