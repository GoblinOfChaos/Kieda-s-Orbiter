#!/usr/bin/env python3
"""Mod Collection tab: shows all mods from ExportUpgrades and ExportModSet with owned counts. Filter to show only missing ones."""
import json
import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QCheckBox,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from column_persistence import apply_saved_widths, remember_widths

POLARITY_NAMES = {
    'AP_ATTACK': 'Madurai',
    'AP_DEFENSE': 'Vazarin',
    'AP_TACTIC': 'Naramon',
    'AP_POWER': 'Zenurik',
    'AP_PRECEPT': 'Penjaga',
    'AP_UMBRA': 'Umbra',
    'AP_UNIVERSAL': 'Universal',
    'AP_WARD': 'Unairu',
    'AP_ANY': 'Aura',
}


class ModCollectionTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._owned = {}
        self._mods = []
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(QLabel("Search:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search mods...")
        self._search.textChanged.connect(self._filter)
        header.addWidget(self._search)

        self._hide_owned = QCheckBox("Hide owned mods")
        self._hide_owned.stateChanged.connect(self._filter)
        header.addWidget(self._hide_owned)

        layout.addLayout(header)

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels([
            "Name", "Type", "Rarity", "Polarity", "Source", "Drop Location", "Owned"
        ])
        for col in range(7):
            self._table.horizontalHeader().setSectionResizeMode(col, QHeaderView.Interactive)
        apply_saved_widths(self._table, "mod_collection_table", [180, 110, 70, 80, 140, 320, 60])
        remember_widths(self._table, "mod_collection_table")
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
            for u in inventory.get('RawUpgrades', [])
            if isinstance(u, dict) and u.get('ItemType')
        }
        wfcd_names, wfcd_drops = self._load_wfcd_data(base / 'wfcd_all_cache.json')
        upgrades = self._load_json(base / 'ExportUpgrades.json') or {}
        mod_sets = self._load_json(base / 'ExportModSet.json') or {}

        sets_by_name = self._build_set_names(mod_sets.keys())

        self._mods = []
        for unique, data in sorted(upgrades.items(), key=lambda kv: kv[0]):
            mod_name = wfcd_names.get(unique)
            if not mod_name:
                mod_name = self._humanize_name(unique)
            mod_type = data.get('type', '')
            rarity = data.get('rarity', '')
            raw_polarity = data.get('polarity', '')
            polarity = POLARITY_NAMES.get(raw_polarity, raw_polarity)
            source = data.get('compatName') or data.get('compat') or ''
            set_name = self._set_for_unique(unique, sets_by_name)
            if set_name:
                source = f"Set: {set_name}"

            owned_count = self._owned.get(unique, 0)
            drop_location = wfcd_drops.get(unique, '') or 'No drop data (check wiki)'
            self._mods.append({
                'name': mod_name,
                'type': mod_type,
                'rarity': rarity,
                'polarity': polarity,
                'source': source,
                'drop_location': drop_location,
                'owned': owned_count,
                'is_set': bool(set_name),
            })

        self._populate_table(self._mods)
        self._status.setText(f"Loaded {len(self._mods)} mods from ExportUpgrades")

    def _load_json(self, path):
        try:
            with path.open() as fh:
                return json.load(fh)
        except Exception:
            return None

    def _load_wfcd_data(self, path):
        try:
            with path.open() as fh:
                data = json.load(fh)
        except Exception:
            return {}, {}

        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get('items') or data.get('data') or []
        names = {}
        drops = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            u = item.get('uniqueName')
            n = item.get('name')
            if u and n:
                names[u] = n
            if u and item.get('drops'):
                locations = sorted({d.get('location') for d in item['drops'] if d.get('location')})
                if locations:
                    drops[u] = '; '.join(locations)
        return names, drops

    def _build_set_names(self, keys):
        results = {}
        for key in keys:
            if not isinstance(key, str):
                continue
            match = re.search(r'/Sets/([^/]+)/', key)
            if match:
                results[key] = match.group(1)
        return results

    def _set_for_unique(self, unique, sets_by_name):
        for key, set_name in sets_by_name.items():
            if key in unique:
                return set_name
        return None

    def _humanize_name(self, unique):
        name = unique.split('/')[-1]
        name = name.replace('Mod', '').replace('Set', '').replace('Augment', 'Augment').strip()
        return re.sub(r'([A-Z])', r' \1', name).replace('  ', ' ').strip()

    def _populate_table(self, mods):
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        for mod in mods:
            r = self._table.rowCount()
            self._table.insertRow(r)
            _a0 = QTableWidgetItem(mod['name']); _a0.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter); self._table.setItem(r, 0, _a0)
            _a1 = QTableWidgetItem(mod['type']); _a1.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter); self._table.setItem(r, 1, _a1)
            _a2 = QTableWidgetItem(mod['rarity']); _a2.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter); self._table.setItem(r, 2, _a2)
            _a3 = QTableWidgetItem(mod['polarity']); _a3.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter); self._table.setItem(r, 3, _a3)
            _a4 = QTableWidgetItem(mod['source']); _a4.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter); self._table.setItem(r, 4, _a4)
            _a5 = QTableWidgetItem(mod['drop_location']); _a5.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter); self._table.setItem(r, 5, _a5)
            owned_item = QTableWidgetItem()
            owned_item.setData(Qt.DisplayRole, mod['owned'])
            owned_item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            self._table.setItem(r, 6, owned_item)
        self._table.setSortingEnabled(True)

    def _filter(self, *_):
        q = self._search.text().strip().lower()
        hide_owned = self._hide_owned.isChecked()

        for r in range(self._table.rowCount()):
            name_item = self._table.item(r, 0)
            type_item = self._table.item(r, 1)
            source_item = self._table.item(r, 4)
            drop_item = self._table.item(r, 5)
            owned_item = self._table.item(r, 6)
            name = name_item.text().lower() if name_item else ''
            typ = type_item.text().lower() if type_item else ''
            source = source_item.text().lower() if source_item else ''
            drop_location = drop_item.text().lower() if drop_item else ''
            owned = 0
            try:
                owned = int(owned_item.text())
            except Exception:
                owned = 0
            visible = True
            if q and q not in name and q not in typ and q not in source and q not in drop_location:
                visible = False
            if hide_owned and owned > 0:
                visible = False
            self._table.setRowHidden(r, not visible)

    def get_selected_mod(self):
        r = self._table.currentRow()
        if r < 0:
            return None
        return self._table.item(r, 0).text()
