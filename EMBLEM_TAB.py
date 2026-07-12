#!/usr/bin/env python3
"""Emblems tab: shows every clan/alliance/event emblem with owned status.
Filter to show only missing.

Unlike mods/arcanes, emblems aren't stackable - WFCD classifies them under
the generic "Skin" type (matched here by "Emblem" appearing in the
uniqueName path instead), and inventory.json tracks them as individual
unique-instance entries under WeaponSkins with no ItemCount field, so
ownership here is Yes/No, not a count."""
import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QCheckBox,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from column_persistence import apply_saved_widths, remember_widths


class EmblemTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._owned = set()
        self._emblems = []
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(QLabel("Search:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search emblems...")
        self._search.textChanged.connect(self._filter)
        header.addWidget(self._search)

        self._hide_owned = QCheckBox("Hide owned emblems")
        self._hide_owned.stateChanged.connect(self._filter)
        header.addWidget(self._hide_owned)

        layout.addLayout(header)

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Name", "Owned"])
        for col in range(2):
            self._table.horizontalHeader().setSectionResizeMode(col, QHeaderView.Interactive)
        apply_saved_widths(self._table, "emblem_table", [320, 70])
        remember_widths(self._table, "emblem_table")
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
            u['ItemType'] for u in inventory.get('WeaponSkins', [])
            if isinstance(u, dict) and u.get('ItemType')
        }

        wfcd = self._load_json(base / 'wfcd_all_cache.json') or []
        items = wfcd if isinstance(wfcd, list) else (wfcd.get('items') or wfcd.get('data') or [])

        self._emblems = []
        for item in items:
            if not isinstance(item, dict) or item.get('type') != 'Skin':
                continue
            uname = item.get('uniqueName', '')
            name = item.get('name', '')
            if not uname or not name or 'Emblem' not in uname:
                continue
            self._emblems.append({'name': name, 'owned': uname in self._owned})

        self._emblems.sort(key=lambda e: e['name'])
        self._populate_table(self._emblems)
        self._status.setText(f"Loaded {len(self._emblems)} emblems")

    def _load_json(self, path):
        try:
            with path.open() as fh:
                return json.load(fh)
        except Exception:
            return None

    def _populate_table(self, emblems):
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        for e in emblems:
            r = self._table.rowCount()
            self._table.insertRow(r)
            _a0 = QTableWidgetItem(e['name']); _a0.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter); self._table.setItem(r, 0, _a0)
            owned_item = QTableWidgetItem("Yes" if e['owned'] else "No")
            owned_item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            if e['owned']:
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
            owned = owned_item.text() == "Yes" if owned_item else False
            visible = True
            if q and q not in name:
                visible = False
            if hide_owned and owned:
                visible = False
            self._table.setRowHidden(r, not visible)
