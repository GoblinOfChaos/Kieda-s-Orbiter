#!/usr/bin/env python3
"""Settings tab: view and edit config.json in-app."""
import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox, QLabel,
    QLineEdit, QSpinBox, QPushButton, QHBoxLayout, QMessageBox,
)

BASE = Path.home() / 'wfinfo-ng'
CONFIG_FILE = BASE / 'config.json'

_FIELDS = [
    # (config_key, label, type, min, max, tooltip)
    ("trigger_pattern", "Trigger pattern",
     "str", None, None,
     "Text that appears in EE.log to trigger a relic reward capture."),
    ("show_notifications", "Desktop notifications (0=off, 1=on)",
     "int", 0, 1,
     "Show a desktop notification when a relic reward is detected. Disable if it pulls focus away from Warframe."),
    ("window_name", "Window name",
     "str", None, None,
     "Name of the Warframe game window (for OCR targeting)."),
    ("pre_capture_sleep_ms", "Pre-capture sleep (ms)",
     "int", 0, 10000,
     "How long to wait after trigger before capturing the screen."),
    ("poll_interval_ms", "Poll interval (ms)",
     "int", 50, 5000,
     "How often orbiter checks EE.log for new triggers."),
    ("display_duration_ms", "Overlay display duration (ms)",
     "int", 5000, 120000,
     "How long the reward overlay stays visible. Default 30000 (30 seconds)."),
    ("ee_log_path", "EE.log path (blank = auto)",
     "str", None, None,
     "Full path to EE.log, or leave blank to auto-detect."),
]


class SettingsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._widgets = {}
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        box = QGroupBox("Capture / OCR settings")
        form = QFormLayout(box)
        form.setLabelAlignment(Qt.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        for key, label, typ, mn, mx, tip in _FIELDS:
            if typ == "int":
                w = QSpinBox()
                w.setRange(mn, mx)
                w.setToolTip(tip)
            else:
                w = QLineEdit()
                w.setPlaceholderText(tip)
                w.setToolTip(tip)
            self._widgets[key] = w
            form.addRow(label + ":", w)

        layout.addWidget(box)

        btn_row = QHBoxLayout()
        self._save_btn = QPushButton("Save settings")
        self._save_btn.clicked.connect(self._save)
        self._reload_btn = QPushButton("Reload from disk")
        self._reload_btn.clicked.connect(self._load)
        btn_row.addStretch()
        btn_row.addWidget(self._reload_btn)
        btn_row.addWidget(self._save_btn)
        layout.addLayout(btn_row)

        self._status = QLabel("")
        layout.addWidget(self._status)
        layout.addStretch()

    def _load(self):
        try:
            cfg = json.loads(CONFIG_FILE.read_text())
        except Exception as e:
            self._status.setText(f"Load error: {e}")
            cfg = {}

        for key, _, typ, _, _, _ in _FIELDS:
            val = cfg.get(key)
            w = self._widgets[key]
            if typ == "int":
                w.setValue(int(val) if val is not None else 0)
            else:
                w.setText(str(val) if val is not None else "")

        self._status.setText(f"Loaded {CONFIG_FILE}")

    def _save(self):
        # Read current config so we preserve any unknown keys
        try:
            cfg = json.loads(CONFIG_FILE.read_text())
        except Exception:
            cfg = {}

        for key, _, typ, _, _, _ in _FIELDS:
            w = self._widgets[key]
            if typ == "int":
                cfg[key] = w.value()
            else:
                raw = w.text().strip()
                cfg[key] = raw if raw else None

        try:
            CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
            self._status.setText(f"Saved to {CONFIG_FILE}")
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))
