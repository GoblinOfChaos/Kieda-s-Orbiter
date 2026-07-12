#!/usr/bin/env python3
"""Ephemeras tab: shows every cosmetic ephemera with owned status and drop
location. Filter to show only missing.

Same data-shape caveats as Emblems: WFCD classifies these under the
generic "Skin" type (matched here by "Ephemera" in the uniqueName path),
and inventory.json tracks them as individual unique-instance entries
under WeaponSkins with no ItemCount - ownership here is Yes/No."""
import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QCheckBox,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from column_persistence import apply_saved_widths, remember_widths


class EphemeraTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._owned = set()
        self._ephemera = []
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(QLabel("Search:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search ephemera...")
        self._search.textChanged.connect(self._filter)
        header.addWidget(self._search)

        self._hide_owned = QCheckBox("Hide owned ephemera")
        self._hide_owned.stateChanged.connect(self._filter)
        header.addWidget(self._hide_owned)

        layout.addLayout(header)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Name", "Drop Location", "Owned"])
        for col in range(3):
            self._table.horizontalHeader().setSectionResizeMode(col, QHeaderView.Interactive)
        apply_saved_widths(self._table, "ephemera_table", [260, 320, 70])
        remember_widths(self._table, "ephemera_table")
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

        self._ephemera = []
        for item in items:
            if not isinstance(item, dict) or item.get('type') != 'Skin':
                continue
            uname = item.get('uniqueName', '')
            name = item.get('name', '')
            if not uname or not name or 'Ephemera' not in uname:
                continue
            locations = sorted({d.get('location') for d in (item.get('drops') or []) if d.get('location')})
            drop_location = '; '.join(locations) if locations else 'No drop data (check wiki)'
            self._ephemera.append({
                'name': name, 'drop_location': drop_location,
                'owned': uname in self._owned,
            })

        self._ephemera.sort(key=lambda e: e['name'])
        self._populate_table(self._ephemera)
        self._status.setText(f"Loaded {len(self._ephemera)} ephemera")

    def _load_json(self, path):
        try:
            with path.open() as fh:
                return json.load(fh)
        except Exception:
            return None

    def _populate_table(self, ephemera):
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        for e in ephemera:
            r = self._table.rowCount()
            self._table.insertRow(r)
            _a0 = QTableWidgetItem(e['name']); _a0.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter); self._table.setItem(r, 0, _a0)
            _a1 = QTableWidgetItem(e['drop_location']); _a1.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter); self._table.setItem(r, 1, _a1)
            owned_item = QTableWidgetItem("Yes" if e['owned'] else "No")
            owned_item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            if e['owned']:
                owned_item.setForeground(Qt.cyan)
            self._table.setItem(r, 2, owned_item)
        self._table.setSortingEnabled(True)

    def _filter(self, *_):
        q = self._search.text().strip().lower()
        hide_owned = self._hide_owned.isChecked()
        for r in range(self._table.rowCount()):
            name_item = self._table.item(r, 0)
            drop_item = self._table.item(r, 1)
            owned_item = self._table.item(r, 2)
            name = name_item.text().lower() if name_item else ''
            drop_location = drop_item.text().lower() if drop_item else ''
            owned = owned_item.text() == "Yes" if owned_item else False
            visible = True
            if q and q not in name and q not in drop_location:
                visible = False
            if hide_owned and owned:
                visible = False
            self._table.setRowHidden(r, not visible)
