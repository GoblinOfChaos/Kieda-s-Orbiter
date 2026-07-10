#!/usr/bin/env python3
"""Status & Tools tab — live status, maintenance actions, and log viewer."""

import json
import os
import subprocess
import sys
import time
from glob import glob
from pathlib import Path

try:
    from paths import get_ee_log_path, get_inventory_path, set_ee_log_path, set_inventory_path, describe_paths, DATA_DIR, WFINFO_DIR
except Exception:
    get_ee_log_path = get_inventory_path = set_ee_log_path = set_inventory_path = describe_paths = None

from PySide6.QtCore import Qt, QTimer, QProcess, QEvent
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea,
    QPushButton, QLabel, QGroupBox, QFormLayout, QTextEdit, QMessageBox,
    QSplitter, QSizePolicy, QLineEdit, QFileDialog, QComboBox,
)


class _ScrollLockCombo(QComboBox):
    """ComboBox that ignores scroll-wheel events entirely.
    Prevents the theme from changing when the user scrolls the page.
    Use the Apply button or press Enter to confirm a selection."""
    def wheelEvent(self, event):
        # Always ignore — scroll wheel on a combo in a scrollable page is
        # almost always accidental.  User must click to open the dropdown.
        event.ignore()
from theme import get_palette, COLOR_GREAT, COLOR_BAD


def _p():
    """Return current theme palette — always fresh."""
    return get_palette()

HOME = Path.home()
HELPER_SRC = HOME / "helper-src"
OWNED_FILE = WFINFO_DIR / "owned_items.json"
INVENTORY_FILE = WFINFO_DIR / "inventory.json"
WFCD_CACHE = WFINFO_DIR / "wfcd_items_cache.json"
OVERLAY_SCRIPT = WFINFO_DIR / "overlay.py"
import sys as _sys
VENV_PYTHON = WFINFO_DIR / (".venv/Scripts/python.exe" if _sys.platform == "win32" else ".venv/bin/python")
STATE_FILE = DATA_DIR / "latest-detection.json"
LOG_FILE = DATA_DIR / "overlay.log"


from platform_utils import is_running, kill_processes


def _pgrep(pattern):
    return is_running(pattern)


def _humanize_age(mtime):
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


def _find_qt_lib_dir():
    matches = glob(str(WFINFO_DIR / ".venv/lib*/python*/site-packages/PySide6/Qt/lib"))
    return matches[0] if matches else None


def _status_html(running):
    if running:
        return '<span style="color: #3eff3e; font-weight: bold;">● Running</span>'
    return '<span style="color: #6a88aa;">○ Not running</span>'


class StatusTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = None
        self._setup_ui()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._update_status)
        self.refresh_timer.start(2000)
        self._update_status()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _card(self, title=None, accent=None):
        """Create a styled card frame using the current theme palette."""
        p = _p()
        if accent is None:
            accent = p['accent_mid']
        frame = QWidget()
        frame.setStyleSheet(
            f"QWidget {{ background: {p['bg_panel']}; border: 1px solid {p['border']}; border-radius: 8px; }}"
        )
        vl = QVBoxLayout(frame)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)
        if title:
            hdr = QWidget()
            hdr.setStyleSheet(
                f"background: {p['bg_header']}; border-bottom: 1px solid {p['border']}; "
                f"border-radius: 8px 8px 0 0;"
            )
            hl = QHBoxLayout(hdr)
            hl.setContentsMargins(12, 7, 12, 7)
            bar = QWidget(); bar.setFixedWidth(3); bar.setFixedHeight(14)
            bar.setStyleSheet(f"background: {accent}; border-radius: 2px;")
            hl.addWidget(bar)
            lbl = QLabel(title)
            lbl.setStyleSheet(f"color: {p['gold']}; font-size: 12px; font-weight: 700; "
                              f"letter-spacing: 0.5px; background: transparent;")
            hl.addWidget(lbl)
            hl.addStretch()
            vl.addWidget(hdr)
        body = QWidget()
        body.setStyleSheet("background: transparent; border: none;")
        vl.addWidget(body)
        return frame, body

    def _action_btn(self, text, tooltip="", primary=False):
        """Styled action button using the current theme palette."""
        p = _p()
        b = QPushButton(text)
        b.setToolTip(tooltip)
        if primary:
            b.setStyleSheet(
                f"QPushButton {{ background: {p['bg_card']}; color: {p['gold']}; border: 1px solid {p['accent_mid']}; "
                f"border-radius: 5px; padding: 8px 16px; font-size: 13px; font-weight: 700; }}"
                f"QPushButton:hover {{ background: {p['bg_panel']}; color: {p['gold_bright']}; border-color: {p['accent']}; }}"
                f"QPushButton:disabled {{ background: {p['bg_input']}; color: {p['fg_dim']}; border-color: {p['border']}; }}"
            )
        else:
            b.setStyleSheet(
                f"QPushButton {{ background: {p['bg_header']}; color: {p['fg']}; border: 1px solid {p['border']}; "
                f"border-radius: 5px; padding: 6px 12px; font-size: 12px; }}"
                f"QPushButton:hover {{ background: {p['bg_card']}; color: {p['gold_bright']}; border-color: {p['accent_mid']}; }}"
                f"QPushButton:disabled {{ color: {p['fg_dim']}; border-color: {p['border']}; }}"
            )
        return b

    def _row_lbl(self, key, val_widget, layout):
        """Add a key: value row to a form-like layout."""
        p = _p()
        row = QHBoxLayout()
        k = QLabel(key)
        k.setStyleSheet(f"color: {p['fg_dim']}; font-size: 12px; background: transparent;")
        k.setFixedWidth(160)
        row.addWidget(k)
        row.addWidget(val_widget)
        row.addStretch()
        layout.addLayout(row)

    def refresh_styles(self):
        """Rebuild the entire tab UI with the current theme. Called on theme change."""
        # Remove all existing widgets and rebuild
        old_layout = self.layout()
        if old_layout:
            while old_layout.count():
                item = old_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            QWidget().setLayout(old_layout)  # hand off old layout to temp widget
        self.process = None
        self._setup_ui()
        # Restart timers
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.start(2000)
        self._update_status()

    def _setup_ui(self):
        p = _p()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {p['bg']}; }}")
        content = QWidget()
        content.setStyleSheet(f"background: {p['bg']};")
        scroll.setWidget(content)
        outer.addWidget(scroll)

        main = QVBoxLayout(content)
        main.setSpacing(10)
        main.setContentsMargins(12, 12, 12, 12)

        # ── Top row: status card + refresh button ─────────────────────────
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        # Status card
        status_frame, status_body = self._card("● LIVE STATUS", "#3eff3e")
        status_layout = QVBoxLayout(status_body)
        status_layout.setContentsMargins(12, 10, 12, 12)
        status_layout.setSpacing(6)

        self.lbl_warframe = QLabel()
        self.lbl_wfinfo   = QLabel()
        self.lbl_overlay  = QLabel()
        self.lbl_refresh  = QLabel()
        self.lbl_count    = QLabel()
        self.lbl_detection= QLabel()

        for label_text, widget in [
            ("Warframe:", self.lbl_warframe),
            ("Detector:", self.lbl_wfinfo),
            ("Overlay:", self.lbl_overlay),
            ("Last refresh:", self.lbl_refresh),
            ("Items in db:", self.lbl_count),
            ("Last detection:", self.lbl_detection),
        ]:
            widget.setStyleSheet(f"color: {p['fg']}; font-size: 12px; background: transparent;")
            self._row_lbl(label_text, widget, status_layout)

        top_row.addWidget(status_frame, stretch=3)

        # Primary refresh button (right of status)
        self.btn_refresh = self._action_btn(
            "\u27f3  Refresh Data",
            "Re-reads inventory.json and rebuilds all data files.\n"
            "Best done in your orbiter or on a loading screen.",
            primary=True
        )
        self.btn_refresh.setMinimumHeight(60)
        self.btn_refresh.clicked.connect(self.refresh_inventory)
        top_row.addWidget(self.btn_refresh, stretch=1)
        main.addLayout(top_row)

        # ── Actions card ──────────────────────────────────────────────────
        act_frame, act_body = self._card("\u2699  ACTIONS", "#c9a84c")
        act_layout = QGridLayout(act_body)
        act_layout.setContentsMargins(12, 10, 12, 12)
        act_layout.setSpacing(8)

        def _abtn(text, tip, slot, r, c, span=1):
            b = self._action_btn(text, tip)
            b.clicked.connect(slot)
            act_layout.addWidget(b, r, c, 1, span)
            return b

        self.btn_update      = _abtn("Update Game Data",        "Refresh prices + item list from warframestat.us",           self.update_data,        0, 0)
        self.btn_refresh_wfcd= _abtn("Refresh WFCD Cache",      "Download fresh item database from WFCD GitHub (~40MB)",     self.refresh_wfcd_cache, 0, 1)
        self.btn_real_prices = _abtn("Fetch Live Prices",        "Get real plat prices from warframe.market — takes ~5 min", self.fetch_real_prices,  1, 0)
        self.btn_reset_cache = _abtn("Clear Cache",              "Delete the WFCD cache so it re-downloads on next refresh",  self.reset_wfcd_cache,   1, 1)
        self.btn_overlay     = _abtn("Restart Overlay",          "Kill and relaunch the reward/relic overlay window",        self.restart_overlay,    2, 0)
        self.btn_test        = _abtn("Test Overlay",             "Write a fake detection so the overlay pops up to test it", self.test_overlay,       2, 1)
        self.btn_reload_cfg  = _abtn("Reload Detector Config",   "Restart the OCR detector to pick up config.json changes",  self.reload_config,      3, 0)
        self.btn_rebuild     = _abtn("Rebuild API Helper",       "Pull + rebuild warframe-api-helper from source",           self.rebuild_helper,     3, 1)
        main.addWidget(act_frame)

        # ── Overlay settings card ─────────────────────────────────────────
        from PySide6.QtWidgets import QComboBox as _CB2
        ov_frame, ov_body = self._card("📺  OVERLAY DISPLAY", p['accent'])
        ol = QVBoxLayout(ov_body)
        ol.setContentsMargins(12, 10, 12, 12)
        ol.setSpacing(10)

        # Monitor selector row
        mon_row = QHBoxLayout()
        mon_lbl = QLabel("Display on:")
        mon_lbl.setStyleSheet(f"color: {p['fg_dim']}; font-size: 12px; background: transparent;")
        mon_lbl.setFixedWidth(100)
        self._monitor_combo = _CB2()
        self._monitor_combo.setFocusPolicy(Qt.StrongFocus)
        self._monitor_combo.setMinimumHeight(30)
        self._monitor_combo.setToolTip(
            "Which monitor the overlay appears on when first shown.\n"
            "You can still drag it anywhere — this only sets the starting position.\n"
            "Use 'Reset Position' to move it back to this monitor's default position."
        )
        self._monitor_combo.wheelEvent = lambda e: e.ignore()  # no accidental scroll

        # Populate with current screens
        from PySide6.QtWidgets import QApplication as _QApp2
        screens = _QApp2.screens()
        self._monitor_combo.addItem("Auto (follow Warframe window)", "auto")
        for i, s in enumerate(screens):
            g = s.geometry()
            name = s.name() or f"Monitor {i+1}"
            primary = " — Primary" if s == _QApp2.primaryScreen() else ""
            self._monitor_combo.addItem(
                f"Monitor {i+1}: {name}  {g.width()}×{g.height()}{primary}", i
            )

        # Load saved value
        try:
            _cfg = json.loads(Path(WFINFO_DIR / "config.json").read_text())
            saved_mon = _cfg.get("overlay_monitor", "auto")
            for idx in range(self._monitor_combo.count()):
                if self._monitor_combo.itemData(idx) == saved_mon:
                    self._monitor_combo.setCurrentIndex(idx)
                    break
        except Exception:
            pass

        mon_row.addWidget(mon_lbl)
        mon_row.addWidget(self._monitor_combo, stretch=1)
        ol.addLayout(mon_row)

        # Reset saved position + save monitor button
        btn_row2 = QHBoxLayout()
        save_mon_btn = self._action_btn("Apply & Reset Position",
            "Save monitor choice and clear the overlay's remembered drag position\n"
            "so it snaps to the new monitor on next detection.")
        reset_pos_btn = self._action_btn("Reset Position Only",
            "Clear the overlay's remembered drag position without changing monitor.")

        def _save_monitor():
            try:
                cfg_path = WFINFO_DIR / "config.json"
                cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
                cfg["overlay_monitor"] = self._monitor_combo.currentData()
                cfg_path.write_text(json.dumps(cfg, indent=2))
                # Clear saved positions for both overlays
                for pos_file in [
                    DATA_DIR / "overlay-position.json",
                    DATA_DIR / "riven-overlay-position.json",
                ]:
                    if pos_file.exists():
                        pos_file.unlink()
                self.lbl_status.setText("Overlay monitor saved. Restart overlay to apply.")
            except Exception as e:
                self.lbl_status.setText(f"Failed to save: {e}")

        def _reset_position():
            for pos_file in [
                DATA_DIR / "overlay-position.json",
                DATA_DIR / "riven-overlay-position.json",
            ]:
                if pos_file.exists():
                    pos_file.unlink()
            self.lbl_status.setText("Overlay position reset. Next detection will reposition.")

        save_mon_btn.clicked.connect(_save_monitor)
        reset_pos_btn.clicked.connect(_reset_position)
        btn_row2.addWidget(save_mon_btn)
        btn_row2.addWidget(reset_pos_btn)
        ol.addLayout(btn_row2)

        hint2 = QLabel("Tip: drag the overlay during a detection to reposition it. That position is saved automatically.")
        hint2.setStyleSheet(f"color: {p['fg_dim']}; font-size: 11px; background: transparent;")
        hint2.setWordWrap(True)
        ol.addWidget(hint2)
        main.addWidget(ov_frame)

        # ── Paths card ────────────────────────────────────────────────────
        paths_frame, paths_body = self._card("\u25a1  FILE PATHS", "#4a90d9")
        pl = QVBoxLayout(paths_body)
        pl.setContentsMargins(12, 10, 12, 12)
        pl.setSpacing(8)

        hint = QLabel("Leave blank to auto-detect. Change only if files are in non-standard locations.")
        hint.setStyleSheet(f"color: {p['fg_dim']}; font-size: 11px; background: transparent;")
        hint.setWordWrap(True)
        pl.addWidget(hint)

        for attr, row_label, placeholder, browse_title, browse_filter in [
            ("_ee_path_edit",  "EE.log:",          "Auto-detect",
             "Find EE.log", "Log files (EE.log *.log);;All files (*)"),
            ("_inv_path_edit", "inventory.json:",  "Auto-detect",
             "Find inventory.json", "JSON files (*.json);;All files (*)"),
        ]:
            row = QHBoxLayout()
            lk = QLabel(row_label)
            lk.setStyleSheet(f"color: {p['fg_dim']}; font-size: 12px; background: transparent;")
            lk.setFixedWidth(120)
            edit = QLineEdit(); edit.setPlaceholderText(placeholder)
            setattr(self, attr, edit)
            brw = self._action_btn("Browse")
            brw.setMaximumWidth(75)
            def _browse(title=browse_title, filt=browse_filter, e=edit):
                path, _ = QFileDialog.getOpenFileName(self, title, str(Path.home()), filt)
                if path: e.setText(path)
            brw.clicked.connect(_browse)
            status_lbl = QLabel("")
            status_lbl.setStyleSheet(f"color: {p['fg_dim']}; font-size: 11px; background: transparent;")
            setattr(self, attr.replace("_edit", "_status_lbl"), status_lbl)
            row.addWidget(lk); row.addWidget(edit, stretch=1)
            row.addWidget(brw); row.addWidget(status_lbl, stretch=1)
            pl.addLayout(row)

        save_row = QHBoxLayout()
        save_btn = self._action_btn("Save Paths", "Save path overrides to config.json")
        save_btn.setMaximumWidth(110)
        save_btn.clicked.connect(self._save_paths)
        save_row.addWidget(save_btn); save_row.addStretch()
        pl.addLayout(save_row)
        main.addWidget(paths_frame)
        self._refresh_path_display()

        # ── Theme picker card (always visible) ───────────────────────────
        from PySide6.QtWidgets import QTableWidget as _QTW, QTableWidgetItem as _QTWI
        from PySide6.QtCore import Qt as _Qt

        theme_frame, theme_body = self._card("🎨  UI THEME", p['gold'])
        tl = QVBoxLayout(theme_body)
        tl.setContentsMargins(12, 10, 12, 12)
        tl.setSpacing(8)

        # Combo + apply row
        theme_row = QHBoxLayout()
        theme_lbl = QLabel("Theme:")
        theme_lbl.setStyleSheet(f"color: {p['fg_dim']}; font-size: 12px; background: transparent;")
        theme_lbl.setFixedWidth(60)
        self._theme_combo = _ScrollLockCombo()
        self._theme_combo.setFocusPolicy(Qt.StrongFocus)
        self._theme_combo.setMinimumHeight(32)
        self._theme_combo.setStyleSheet(
            f"QComboBox {{ background-color: {p['bg_input']}; color: {p['fg']}; "
            f"border: 2px solid {p['accent_mid']}; border-radius: 5px; "
            f"padding: 5px 8px; padding-right: 26px; font-size: 13px; }}"
            f"QComboBox:hover {{ border: 2px solid {p['accent']}; }}"
            f"QComboBox:focus {{ border: 2px solid {p['accent']}; }}"
            f"QComboBox::drop-down {{ subcontrol-origin: padding; "
            f"subcontrol-position: top right; width: 26px; "
            f"border-left: 1px solid {p['accent_mid']}; "
            f"border-radius: 0 4px 4px 0; background-color: {p['bg_panel']}; }}"
            f"QComboBox QAbstractItemView {{ background-color: {p['bg_card']}; "
            f"color: {p['fg']}; selection-background-color: {p['accent_mid']}; "
            f"selection-color: #ffffff; border: 2px solid {p['accent_mid']}; "
            f"border-radius: 4px; outline: 0; padding: 2px; }}"
        )

        apply_btn = self._action_btn("Apply")
        apply_btn.setMaximumWidth(70)
        theme_row.addWidget(theme_lbl)
        theme_row.addWidget(self._theme_combo, stretch=1)
        theme_row.addWidget(apply_btn)
        tl.addLayout(theme_row)

        # Colorblind info label
        self._cb_info_lbl = QLabel("")
        self._cb_info_lbl.setStyleSheet(
            f"color: {p['fg']}; font-size: 11px; background: {p['bg_input']}; "
            f"border: 1px solid {p['border']}; border-radius: 4px; padding: 4px 8px;"
        )
        self._cb_info_lbl.setWordWrap(True)
        tl.addWidget(self._cb_info_lbl)

        # Colorblind reference chart
        chart_lbl = QLabel("Colorblindness Reference")
        chart_lbl.setStyleSheet(
            f"color: {p['fg_dim']}; font-size: 11px; font-weight: 600; background: transparent;"
        )
        tl.addWidget(chart_lbl)

        chart = _QTW(6, 3)
        chart.setHorizontalHeaderLabels(["Theme", "Warframe School", "Safe For"])
        chart.verticalHeader().setVisible(False)
        chart.setEditTriggers(_QTW.NoEditTriggers)
        chart.setStyleSheet(
            f"background: {p['bg']}; color: {p['fg']}; gridline-color: {p['border']}; "
            f"border: 1px solid {p['border']}; border-radius: 4px; font-size: 11px;"
            f"QHeaderView::section {{ background: {p['bg_header']}; color: {p['gold']}; "
            f"font-weight: 700; border-bottom: 1px solid {p['accent_mid']}; padding: 3px 6px; }}"
        )
        from PySide6.QtWidgets import QHeaderView as _QHV
        chart.horizontalHeader().setSectionResizeMode(0, _QHV.ResizeToContents)
        chart.horizontalHeader().setSectionResizeMode(1, _QHV.ResizeToContents)
        chart.horizontalHeader().setSectionResizeMode(2, _QHV.Stretch)
        chart.setFixedHeight(160)

        THEME_CB_INFO = {
            "Kieda's Default": ("Sapphire blue + metallic gold",
                                "Standard — no specific colorblind optimization",
                                "#d8eaf8"),
            "Madurai":         ("Deep crimson + fire orange",
                                "\u2705 Safe for Deuteranopia (red-green) \u2014 uses orange/amber, no green",
                                "#ff8c3a"),
            "Vazarin":         ("Deep navy + cyan/white",
                                "\u2705 Safe for Protanopia (red-blind) \u2014 blue/white spectrum only",
                                "#38b6e8"),
            "Naramon":         ("Charcoal black + white/amber",
                                "\u2705 Safe for ALL colorblindness types \u2014 high contrast monochrome",
                                "#f0f0f0"),
            "Unairu":          ("Deep earth brown + desert amber",
                                "\u2705 Safe for Deuteranopia + Protanopia \u2014 warm amber/tan, no red/green",
                                "#e8c060"),
            "Zenurik":         ("Deep indigo + electric violet",
                                "\u2705 Safe for Tritanopia (blue-yellow) \u2014 purple base avoids blue-yellow confusion",
                                "#b060ff"),
        }
        CHART_ROWS = [
            ("Kieda's Default", "—",        "Standard (no optimization)"),
            ("Madurai",         "Offense",  "Deuteranopia, Protanopia"),
            ("Vazarin",         "Defense",  "Protanopia"),
            ("Naramon",         "Precision","ALL types + low vision"),
            ("Unairu",          "Endurance","Deuteranopia, Protanopia"),
            ("Zenurik",         "Energy",   "Tritanopia"),
        ]
        CHART_COLORS = ["#d8eaf8","#ff8c3a","#38b6e8","#f0f0f0","#e8c060","#b060ff"]
        for r, (theme_name, school, safe_for) in enumerate(CHART_ROWS):
            color = CHART_COLORS[r]
            for c, text in enumerate([theme_name, school, safe_for]):
                item = _QTWI(text)
                item.setForeground(__import__('PySide6.QtGui', fromlist=['QColor']).QColor(color))
                item.setTextAlignment(_Qt.AlignLeft | _Qt.AlignVCenter)
                chart.setItem(r, c, item)
        tl.addWidget(chart)
        main.addWidget(theme_frame)

        try:
            from theme import THEMES, save_theme, load_theme, get_theme
            for name in THEMES:
                self._theme_combo.addItem(name)
            current = load_theme()
            idx = list(THEMES.keys()).index(current) if current in THEMES else 0
            self._theme_combo.setCurrentIndex(idx)

            def _update_cb_info(name):
                info = THEME_CB_INFO.get(name)
                if info:
                    colors_str, cb_str, accent = info
                    self._cb_info_lbl.setText(
                        f"<b style='color:{accent};'>{name}</b>  \u2014  {colors_str}<br>"
                        f"<span style='color:{_p()['fg']};'>{cb_str}</span>"
                    )
                    self._cb_info_lbl.setTextFormat(_Qt.RichText)

            def _apply_theme(name=None):
                name = name or self._theme_combo.currentText()
                save_theme(name)
                from PySide6.QtWidgets import QApplication
                QApplication.instance().setStyleSheet(get_theme(name))
                self._theme_combo.setCurrentText(name)
                _update_cb_info(name)
                # Refresh main window chrome (sidebar, title bar, nav)
                try:
                    from PySide6.QtWidgets import QApplication
                    for widget in QApplication.topLevelWidgets():
                        if hasattr(widget, '_apply_chrome_styles'):
                            widget._apply_chrome_styles()
                except Exception:
                    pass
                # Rebuild this tab and all loaded sibling pages
                self.refresh_styles()
                try:
                    # Walk up to find the QStackedWidget that holds all pages
                    stack = self.parent()
                    while stack and not hasattr(stack, 'count'):
                        stack = stack.parent()
                    if stack:
                        for i in range(stack.count()):
                            w = stack.widget(i)
                            if w is not self and hasattr(w, 'refresh_styles'):
                                w.refresh_styles()
                            elif w is not self and hasattr(w, '_apply_styles'):
                                w._apply_styles()
                except Exception:
                    pass

            # highlighted fires when the user mouses over a dropdown item —
            # safe for info preview, never triggers on scroll or programmatic changes.
            self._theme_combo.highlighted.connect(
                lambda idx: _update_cb_info(self._theme_combo.itemText(idx))
            )
            # Apply button is the ONLY way to actually save + apply the theme.
            apply_btn.clicked.connect(lambda: _apply_theme(self._theme_combo.currentText()))
            _update_cb_info(current)
        except Exception:
            pass

        # ── Update checker card ───────────────────────────────────────────
        import threading, urllib.request
        upd_frame, upd_body = self._card("⬆  UPDATES", p['green'])
        ul = QVBoxLayout(upd_body)
        ul.setContentsMargins(12, 10, 12, 12)
        ul.setSpacing(8)

        upd_status = QLabel("Click 'Check for Updates' to check.")
        upd_status.setWordWrap(True)
        upd_status.setStyleSheet(f"color: {p['fg']}; font-size: 12px; background: transparent;")
        ul.addWidget(upd_status)

        upd_btn = self._action_btn("Check for Updates",
            "Checks GitHub for a newer version of Kieda's Orbiter")
        ul.addWidget(upd_btn)

        def _do_check():
            upd_btn.setEnabled(False)
            upd_status.setText("Checking…")

            def _run():
                results = []
                # ── App version ──────────────────────────────────────────
                try:
                    version_file = Path(__file__).parent / "VERSION"
                    current = version_file.read_text().strip() if version_file.exists() else "unknown"
                    base_url = "https://github.com/GoblinOfChaos/Kiedas-Orbiter/releases"
                    latest = None

                    # Try releases API first
                    try:
                        req = urllib.request.Request(
                            "https://api.github.com/repos/GoblinOfChaos/Kiedas-Orbiter/releases/latest",
                            headers={"User-Agent": "kiedas-orbiter/1.0", "Accept": "application/vnd.github+json"}
                        )
                        with urllib.request.urlopen(req, timeout=8) as r:
                            data = json.loads(r.read())
                        latest = data.get("tag_name", "").lstrip("v")
                        base_url = data.get("html_url", base_url)
                    except Exception:
                        pass

                    # Fall back to tags API if no release exists yet
                    if not latest:
                        req2 = urllib.request.Request(
                            "https://api.github.com/repos/GoblinOfChaos/Kiedas-Orbiter/tags",
                            headers={"User-Agent": "kiedas-orbiter/1.0", "Accept": "application/vnd.github+json"}
                        )
                        with urllib.request.urlopen(req2, timeout=8) as r:
                            tags = json.loads(r.read())
                        if tags:
                            latest = tags[0]["name"].lstrip("v")

                    if not latest:
                        results.append("?  App:  could not determine latest version")
                    elif latest == current:
                        results.append(f"✓  App:  v{current}  (up to date)")
                    else:
                        results.append(f"⬆  App:  v{current}  →  v{latest} available!\n   {base_url}")
                except Exception as e:
                    results.append(f"?  App:  could not check ({e})")

                # ── PySide6 ──────────────────────────────────────────────
                try:
                    import PySide6
                    installed = PySide6.__version__
                    req2 = urllib.request.Request(
                        "https://pypi.org/pypi/PySide6/json",
                        headers={"User-Agent": "kiedas-orbiter/1.0"}
                    )
                    with urllib.request.urlopen(req2, timeout=8) as r:
                        pdata = json.loads(r.read())
                    pypi_latest = pdata["info"]["version"]
                    if installed == pypi_latest:
                        results.append(f"✓  PySide6:  {installed}  (up to date)")
                    else:
                        results.append(f"⬆  PySide6:  {installed}  →  {pypi_latest} available\n   Run: .venv/bin/pip install --upgrade PySide6")
                except Exception as e:
                    results.append(f"?  PySide6:  could not check ({e})")

                # ── Post back to UI thread ────────────────────────────────
                from PySide6.QtCore import QMetaObject, Qt as _Qt2, Q_ARG
                text = "\n".join(results)
                QMetaObject.invokeMethod(
                    upd_status, "setText",
                    _Qt2.ConnectionType.QueuedConnection,
                    Q_ARG(str, text)
                )
                QMetaObject.invokeMethod(
                    upd_btn, "setEnabled",
                    _Qt2.ConnectionType.QueuedConnection,
                    Q_ARG(bool, True)
                )

            threading.Thread(target=_run, daemon=True).start()

        upd_btn.clicked.connect(_do_check)
        main.addWidget(upd_frame)

        # ── Advanced Settings (collapsible) ───────────────────────────────
        adv_toggle = QPushButton("\u25b6  Advanced Settings (OCR / Detector config)")
        adv_toggle.setCheckable(True)
        adv_toggle.setStyleSheet(
            f"QPushButton {{ text-align: left; padding: 8px 14px; background: {p['bg_header']}; "
            f"color: {p['accent_mid']}; border: 1px solid {p['border']}; border-radius: 5px; "
            f"font-size: 12px; font-weight: 600; }}"
            f"QPushButton:checked {{ color: {p['gold']}; border-color: {p['gold']}; }}"
            f"QPushButton:hover {{ color: {p['accent']}; background: {p['bg_card']}; }}"
        )
        main.addWidget(adv_toggle)

        self._adv_widget = QWidget()
        self._adv_widget.setVisible(False)
        self._adv_widget.setStyleSheet(
            f"background: {p['bg_panel']}; border: 1px solid {p['border']}; border-radius: 6px;"
        )
        adv_layout = QVBoxLayout(self._adv_widget)
        adv_layout.setContentsMargins(12, 10, 12, 10)

        warn = QLabel("\u26a0  These settings affect the OCR detector. Only change if you know what you're doing.")
        warn.setStyleSheet(f"color: {p['gold_bright']}; font-size: 11px; background: transparent;")
        warn.setWordWrap(True)
        adv_layout.addWidget(warn)
        try:
            from SETTINGS_TAB import SettingsTab
            self._settings_widget = SettingsTab()
            adv_layout.addWidget(self._settings_widget)
        except Exception:
            adv_layout.addWidget(QLabel("Settings failed to load."))
        main.addWidget(self._adv_widget)

        def _toggle_adv(checked):
            self._adv_widget.setVisible(checked)
            adv_toggle.setText(
                ("\u25bc" if checked else "\u25b6") + "  Advanced Settings (OCR / Detector config)"
            )
        adv_toggle.toggled.connect(_toggle_adv)

        # ── Logs card ─────────────────────────────────────────────────────
        logs_frame, logs_body = self._card("\u25a0  OUTPUT LOG", "#2e6db4")
        ll = QVBoxLayout(logs_body)
        ll.setContentsMargins(12, 10, 12, 12)
        ll.setSpacing(6)

        log_tabs_row = QHBoxLayout()
        self._log_tab_overlay = self._action_btn("Overlay Log", "Show the live overlay log")
        self._log_tab_cmd = self._action_btn("Command Output", "Show command output from maintenance actions")
        self._log_tab_overlay.setCheckable(True); self._log_tab_overlay.setChecked(True)
        self._log_tab_cmd.setCheckable(True)
        log_tabs_row.addWidget(self._log_tab_overlay)
        log_tabs_row.addWidget(self._log_tab_cmd)
        log_tabs_row.addStretch()
        ll.addLayout(log_tabs_row)

        from PySide6.QtWidgets import QStackedWidget
        self._log_stack = QStackedWidget()

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("monospace", 9))
        self.log_text.setStyleSheet(
            f"background: {p['bg']}; color: {p['fg']}; border: 1px solid {p['border']}; "
            f"border-radius: 4px; selection-background-color: {p['bg_input']};"
        )
        self.log_text.setMinimumHeight(140)
        self._log_stack.addWidget(self.log_text)

        self.cmd_text = QTextEdit()
        self.cmd_text.setReadOnly(True)
        self.cmd_text.setFont(QFont("monospace", 9))
        self.cmd_text.setStyleSheet(
            f"background: {p['bg']}; color: {p['fg']}; border: 1px solid {p['border']}; "
            f"border-radius: 4px; selection-background-color: {p['bg_input']};"
        )
        self.cmd_text.setMinimumHeight(140)
        self._log_stack.addWidget(self.cmd_text)

        def _show_log(idx, btn_on, btn_off):
            self._log_stack.setCurrentIndex(idx)
            btn_on.setChecked(True); btn_off.setChecked(False)
        self._log_tab_overlay.clicked.connect(lambda: _show_log(0, self._log_tab_overlay, self._log_tab_cmd))
        self._log_tab_cmd.clicked.connect(lambda: _show_log(1, self._log_tab_cmd, self._log_tab_overlay))

        ll.addWidget(self._log_stack)
        main.addWidget(logs_frame, stretch=1)

        # ── Status bar ────────────────────────────────────────────────────
        self.lbl_status = QLabel("Idle")
        self.lbl_status.setStyleSheet(
            f"padding: 5px 10px; background: {p['bg']}; color: {p['fg_dim']}; "
            f"border-top: 1px solid {p['border']}; font-size: 11px;"
        )
        outer.addWidget(self.lbl_status)

    # ── Path helpers ──────────────────────────────────────────────────────

    def _refresh_path_display(self):
        if describe_paths is None:
            return
        try:
            info = describe_paths()
            ee = info["ee_log"]
            inv = info["inventory"]

            self._ee_path_edit.setText("" if not ee["is_override"] else ee["path"])
            if ee["exists"]:
                self._ee_status_lbl.setText(f"✓  Found: {ee['path']}")
                self._ee_status_lbl.setStyleSheet(f"font-size: 11px; color: {COLOR_GREAT};")
            else:
                self._ee_status_lbl.setText(f"✗  Not found: {ee['path']}")
                self._ee_status_lbl.setStyleSheet(f"font-size: 11px; color: {COLOR_BAD};")

            self._inv_path_edit.setText("" if not inv["is_override"] else inv["path"])
            if inv["exists"]:
                self._inv_status_lbl.setText(f"✓  Found: {inv['path']}")
                self._inv_status_lbl.setStyleSheet(f"font-size: 11px; color: {COLOR_GREAT};")
            else:
                self._inv_status_lbl.setText(f"✗  Not found: {inv['path']}")
                self._inv_status_lbl.setStyleSheet(f"font-size: 11px; color: {COLOR_BAD};")
        except Exception as e:
            pass

    def _save_paths(self):
        if set_ee_log_path is None:
            return
        set_ee_log_path(self._ee_path_edit.text())
        set_inventory_path(self._inv_path_edit.text())
        self._refresh_path_display()
        self.lbl_status.setText("Paths saved to config.json")

    # ── Status updates ────────────────────────────────────────────────────

    def _update_status(self):
        self.lbl_warframe.setText(_status_html(_pgrep("Warframe.x64.exe")))
        self.lbl_wfinfo.setText(_status_html(_pgrep("target/release/orbiter")))
        self.lbl_overlay.setText(_status_html(_pgrep("overlay.py")))

        if OWNED_FILE.exists():
            self.lbl_refresh.setText(_humanize_age(OWNED_FILE.stat().st_mtime))
            try:
                owned = json.loads(OWNED_FILE.read_text())
                total = len(owned)
                need = sum(1 for v in owned.values()
                           if (isinstance(v, int) and v == 0)
                           or (isinstance(v, dict) and v.get("status") == "NEED"))
                self.lbl_count.setText(f"{total} total  ({need} NEED · {total-need} owned)")
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
                age = _humanize_age(STATE_FILE.stat().st_mtime)
                short = " / ".join(n[:22] for n in names)
                self.lbl_detection.setText(f"{age}: {short}")
            except Exception:
                self.lbl_detection.setText(_humanize_age(STATE_FILE.stat().st_mtime))
        else:
            self.lbl_detection.setText("(none yet)")

        # Tail the overlay log
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
                    self.log_text.verticalScrollBar().setValue(
                        self.log_text.verticalScrollBar().maximum()
                    )
            except OSError:
                pass

    # ── Command runner ────────────────────────────────────────────────────

    def _all_buttons(self):
        return [self.btn_refresh, self.btn_update, self.btn_reset_cache,
                self.btn_rebuild, self.btn_overlay, self.btn_test,
                self.btn_reload_cfg, self.btn_refresh_wfcd, self.btn_real_prices]

    def _set_buttons_enabled(self, enabled):
        for b in self._all_buttons():
            b.setEnabled(enabled)

    def _run_command(self, cmd, cwd, description, reload_tabs=False):
        if self.process and self.process.state() != QProcess.NotRunning:
            QMessageBox.warning(self, "Busy", "Another command is already running.")
            return
        self._pending_reload_tabs = reload_tabs
        self._set_buttons_enabled(False)
        self.lbl_status.setText(f"Running: {description}")
        self.cmd_text.clear()
        self.cmd_text.append(f"=== {description} ===\n")

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._process_output)
        self.process.finished.connect(self._process_finished)
        self.process.setWorkingDirectory(str(cwd))
        self.process.start("/bin/bash", ["-c", cmd])

    def _process_output(self):
        if self.process:
            data = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
            self.cmd_text.append(data.rstrip())
            self.cmd_text.verticalScrollBar().setValue(
                self.cmd_text.verticalScrollBar().maximum()
            )

    def _process_finished(self, code, _status):
        self.cmd_text.append(f"\n=== Finished (exit code {code}) ===")
        self.lbl_status.setText(f"Done (exit {code})")
        self._set_buttons_enabled(True)
        self.process = None
        self._update_status()
        if getattr(self, '_pending_reload_tabs', False) and code == 0:
            self._reload_all_tabs()
            self._pending_reload_tabs = False

    def _reload_all_tabs(self):
        """Walk the QStackedWidget and call _load_data() or _load() on every
        already-built tab so inventory changes appear without restarting."""
        reloaded = []
        try:
            stack = self.parent()
            while stack and not hasattr(stack, 'count'):
                stack = stack.parent()
            if not stack:
                return
            for i in range(stack.count()):
                w = stack.widget(i)
                # Skip placeholders (lazy-unbuilt pages have _factory attr)
                if hasattr(w, '_factory'):
                    continue
                for method in ('_load_data', '_load', 'reload'):
                    if hasattr(w, method) and callable(getattr(w, method)):
                        try:
                            getattr(w, method)()
                            reloaded.append(type(w).__name__)
                        except Exception:
                            pass
                        break
        except Exception:
            pass
        if reloaded:
            self.cmd_text.append(
                f"\n✓ Reloaded tabs: {', '.join(reloaded)}"
            )

    # ── Button handlers ───────────────────────────────────────────────────

    def reload_config(self):
        self._run_command(
            "echo 'Current config:'; cat ~/wfinfo-ng/config.json; echo; "
            "echo 'Restarting orbiter...'; pkill -x orbiter || true; sleep 1; "
            "nohup ./launch-orbiter.sh > " + str(DATA_DIR) + "/orbiter.log 2>&1 & disown; "
            "sleep 2; echo 'wfinfo restarted:'; head -15 " + str(DATA_DIR) + "/orbiter.log",
            cwd=WFINFO_DIR, description="Reload orbiter config",
        )

    def refresh_inventory(self):
        inv = INVENTORY_FILE
        if inv.is_symlink():
            target = inv.resolve()
            if not target.exists():
                QMessageBox.warning(
                    self, "Inventory data missing",
                    f"inventory.json symlink points at {target} but the file doesn't exist."
                )
                return
            age_min = (time.time() - target.stat().st_mtime) / 60
        else:
            if not inv.exists():
                QMessageBox.warning(self, "No inventory data",
                    "inventory.json doesn't exist.")
                return
            age_min = (time.time() - inv.stat().st_mtime) / 60

        if age_min > 30:
            reply = QMessageBox.question(
                self, "Inventory data is stale",
                f"inventory.json is {age_min:.0f} minutes old. Refresh anyway?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        self._run_command(
            "python3 populate_owned.py inventory.json owned_items.json && "
            "python3 populate_crafted.py && python3 populate_relics.py && "
            "python3 populate_equipment.py && python3 record_stats_snapshot.py && "
            "echo 'Done — reloading all tabs...'",
            cwd=WFINFO_DIR, description="Refresh data from inventory",
            reload_tabs=True,
        )

    def refresh_wfcd_cache(self):
        self._run_command(
            "python3 refresh_wfcd_cache.py --force && "
            "echo 'Cache refreshed. Run Update Warframe Data to rebuild.'",
            cwd=WFINFO_DIR, description="Refresh WFCD cache from GitHub",
        )

    def fetch_real_prices(self):
        self._run_command(
            "python3 enrich_prices_from_market.py && echo 'Prices updated.'",
            cwd=WFINFO_DIR, description="Fetch real prices from warframe.market",
        )

    def update_data(self):
        self._run_command("./update.sh", cwd=WFINFO_DIR,
                          description="Update Warframe data")

    def reset_wfcd_cache(self):
        try:
            if WFCD_CACHE.exists():
                WFCD_CACHE.unlink()
                QMessageBox.information(self, "Done",
                    "WFCD cache deleted. It will re-download on the next refresh.")
            else:
                QMessageBox.information(self, "Already gone",
                    "WFCD cache file doesn't exist; nothing to delete.")
        except OSError as e:
            QMessageBox.critical(self, "Failed", f"Could not delete cache: {e}")

    def rebuild_helper(self):
        if not HELPER_SRC.exists():
            QMessageBox.critical(self, "Missing", f"{HELPER_SRC} not found.")
            return
        self._run_command(
            "git pull && ./build.sh && cp warframe-api-helper ~/wfinfo-ng/",
            cwd=HELPER_SRC, description="Rebuild helper",
        )

    def restart_overlay(self):
        kill_processes("overlay.py")
        time.sleep(0.5)
        from platform_utils import launch_detached, clean_env_for_launch
        launch_detached(
            [str(VENV_PYTHON), str(WFINFO_DIR / "launcher.py"), "overlay"],
            cwd=WFINFO_DIR,
            env=clean_env_for_launch(),
            log_file=DATA_DIR / "overlay.log",
        )
        self.lbl_status.setText("Overlay restarted.")
        self._update_status()

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
                {"name": "Tenora Prime Blueprint",          "status": "OWNED", "count": 3},
                {"name": "Harrow Prime Systems Blueprint",  "status": "NEED",  "count": 0},
                {"name": "Forma Blueprint",                 "status": "OWNED", "count": 12},
            ],
        }
        STATE_FILE.write_text(json.dumps(state))
        self.lbl_status.setText("Wrote fake detection state. Overlay should pop up.")