#!/usr/bin/env python3
"""Captura Scenes tab: shows every Captura backdrop scene with owned
counts. Filter to show only missing."""
import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QCheckBox,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from column_persistence import apply_saved_widths, remember_widths


class CapturaTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._owned = {}
        self._scenes = []
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(QLabel("Search:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search Captura scenes...")
        self._search.textChanged.connect(self._filter)
        header.addWidget(self._search)

        self._hide_owned = QCheckBox("Hide owned scenes")
        self._hide_owned.stateChanged.connect(self._filter)
        header.addWidget(self._hide_owned)

        layout.addLayout(header)

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Name", "Owned"])
        for col in range(2):
            self._table.horizontalHeader().setSectionResizeMode(col, QHeaderView.Interactive)
        apply_saved_widths(self._table, "captura_table", [320, 70])
        remember_widths(self._table, "captura_table")
        self._table.setSortingEnabled(True)
        self._table.verticalHeader().setVisible(False)
        self._table.sortByColumn(0, Qt.AscendingOrder)
        layout.addWidget(self._table)

        self._status = QLabel("")
        layout.addWidget(self._status)

    def _load(self):
        base = Path(__file__).parent
        inventory = self._load_json(base / 'inventory.json') or {}
        self._owned = {
            u['ItemType']: u.get('ItemCount', 0)
            for u in inventory.get('MiscItems', [])
            if isinstance(u, dict) and u.get('ItemType')
        }

        wfcd = self._load_json(base / 'wfcd_all_cache.json') or []
        items = wfcd if isinstance(wfcd, list) else (wfcd.get('items') or wfcd.get('data') or [])

        self._scenes = []
        for item in items:
            if not isinstance(item, dict) or item.get('type') != 'Captura':
                continue
            uname = item.get('uniqueName', '')
            name = item.get('name', '')
            if not uname or not name:
                continue
            self._scenes.append({'name': name, 'owned': self._owned.get(uname, 0)})

        self._scenes.sort(key=lambda s: s['name'])
        self._populate_table(self._scenes)
        self._status.setText(f"Loaded {len(self._scenes)} Captura scenes")

    def _load_json(self, path):
        try:
            with path.open() as fh:
                return json.load(fh)
        except Exception:
            return None

    def _populate_table(self, scenes):
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        for s in scenes:
            r = self._table.rowCount()
            self._table.insertRow(r)
            _a0 = QTableWidgetItem(s['name']); _a0.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter); self._table.setItem(r, 0, _a0)
            owned_item = QTableWidgetItem()
            owned_item.setData(Qt.DisplayRole, s['owned'])
            owned_item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            if s['owned'] > 0:
                owned_item.setForeground(Qt.cyan)
            self._table.setItem(r, 1, owned_item)
        self._table.setSortingEnabled(True)

    def _filter(self, *_):
        q = self._search.text().strip().lower()
        hide_owned = self._hide_owned.isChecked()
        for r in range(self._table.rowCount()):
            name_item = self._table.item(r, 0)
            owned_item = self._table.item(r, 1)
            name = name_item.text().lower() if name_item else ''
            owned = owned_item.data(Qt.DisplayRole) if owned_item else 0
            visible = True
            if q and q not in name:
                visible = False
            if hide_owned and (owned or 0) > 0:
                visible = False
            self._table.setRowHidden(r, not visible)
