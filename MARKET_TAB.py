#!/usr/bin/env python3
"""Market Analytics tab: prime parts ranked by plat price, with ducat and trading info."""
import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QCheckBox,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView
)
from column_persistence import apply_saved_widths, remember_widths
from paths import WFINFO_DIR as BASE

PRICES_FILE = BASE / 'prices.json'
ITEMS_FILE  = BASE / 'filtered_items.json'
OWNED_FILE  = BASE / 'owned_items.json'


def _sorted_item(value, *, numeric=False):
    it = QTableWidgetItem()
    if numeric:
        it.setData(Qt.DisplayRole, value)
    else:
        it.setText(str(value))
    it.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
    return it


class MarketTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel("Search:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter by name or equipment")
        self._search.textChanged.connect(self._filter)
        top.addWidget(self._search)

        top.addWidget(QLabel("Min plat:"))
        self._min_plat = QLineEdit("0")
        self._min_plat.setFixedWidth(60)
        self._min_plat.textChanged.connect(self._filter)
        top.addWidget(self._min_plat)

        self._owned_only = QCheckBox("Owned items only")
        self._owned_only.stateChanged.connect(self._filter)
        top.addWidget(self._owned_only)

        self._hide_zero = QCheckBox("Hide 0p items")
        self._hide_zero.setChecked(True)
        self._hide_zero.stateChanged.connect(self._filter)
        top.addWidget(self._hide_zero)

        layout.addLayout(top)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels([
            "Name", "Equipment", "Plat", "Ducats", "Plat/Ducat", "Owned"
        ])
        h = self._table.horizontalHeader()
        for col in range(6):
            h.setSectionResizeMode(col, QHeaderView.Interactive)
        apply_saved_widths(self._table, "market_table", [220, 160, 70, 70, 90, 70])
        remember_widths(self._table, "market_table")
        self._table.setSortingEnabled(True)
        self._table.verticalHeader().setVisible(False)
        self._table.sortByColumn(0, Qt.AscendingOrder)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self._table)

        self._status = QLabel("")
        layout.addWidget(self._status)

    def _load(self):
        try:
            price_list = json.loads(PRICES_FILE.read_text())
            prices = {p['name']: float(p.get('custom_avg') or 0) for p in price_list if 'name' in p}
        except Exception:
            prices = {}

        try:
            fi = json.loads(ITEMS_FILE.read_text())
            eqmt = fi.get('eqmt') or {}
        except Exception:
            eqmt = {}

        try:
            owned = json.loads(OWNED_FILE.read_text())
        except Exception:
            owned = {}

        # part -> (equipment, ducats)
        part_eq = {}
        part_duc = {}
        for eq_name, eq in eqmt.items():
            for pname, pdata in (eq.get('parts') or {}).items():
                part_eq[pname] = eq_name
                part_duc[pname] = pdata.get('ducats', 0) if isinstance(pdata, dict) else 0

        self._rows = []
        for name, plat in prices.items():
            eq = part_eq.get(name, '')
            duc = part_duc.get(name, 0)
            ratio = round(plat / duc, 2) if duc > 0 else 0.0
            own = owned.get(name, 0)
            self._rows.append({
                'name': name, 'eq': eq, 'plat': plat, 'duc': duc,
                'ratio': ratio, 'owned': own,
            })

        # Sort by plat descending by default
        self._rows.sort(key=lambda r: r['plat'], reverse=True)
        self._populate()

    def _populate(self):
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        for row in self._rows:
            r = self._table.rowCount()
            self._table.insertRow(r)

            _a0 = QTableWidgetItem(row['name']); _a0.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter); self._table.setItem(r, 0, _a0)
            _a1 = QTableWidgetItem(row['eq']); _a1.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter); self._table.setItem(r, 1, _a1)

            plat_it = _sorted_item(row['plat'], numeric=True)
            if row['plat'] >= 20:
                plat_it.setForeground(QColor('#2ecc71'))
            elif row['plat'] >= 5:
                plat_it.setForeground(QColor('#f1c40f'))
            self._table.setItem(r, 2, plat_it)

            self._table.setItem(r, 3, _sorted_item(row['duc'], numeric=True))
            self._table.setItem(r, 4, _sorted_item(row['ratio'], numeric=True))

            owned_it = _sorted_item(row['owned'], numeric=True)
            if row['owned'] > 0:
                owned_it.setForeground(QColor('#3498db'))
            self._table.setItem(r, 5, owned_it)

        self._table.setSortingEnabled(True)
        self._status.setText(f"Loaded {len(self._rows)} items with price data")

    def _filter(self, *_):
        q = self._search.text().strip().lower()
        owned_only = self._owned_only.isChecked()
        hide_zero = self._hide_zero.isChecked()
        try:
            min_plat = float(self._min_plat.text())
        except ValueError:
            min_plat = 0.0

        for r in range(self._table.rowCount()):
            name_it  = self._table.item(r, 0)
            eq_it    = self._table.item(r, 1)
            plat_it  = self._table.item(r, 2)
            owned_it = self._table.item(r, 5)
            name  = name_it.text().lower() if name_it else ''
            eq    = eq_it.text().lower() if eq_it else ''
            plat  = plat_it.data(Qt.DisplayRole) if plat_it else 0
            owned = owned_it.data(Qt.DisplayRole) if owned_it else 0

            visible = True
            if q and q not in name and q not in eq:
                visible = False
            if owned_only and owned == 0:
                visible = False
            if hide_zero and (plat or 0) == 0:
                visible = False
            if (plat or 0) < min_plat:
                visible = False
            self._table.setRowHidden(r, not visible)
