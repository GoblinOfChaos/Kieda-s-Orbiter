#!/usr/bin/env python3
"""Mod Collection tab: shows all mods from ExportUpgrades and ExportModSet with owned counts. Filter to show only missing ones."""
import json
import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QCheckBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox
)
from column_persistence import apply_saved_widths, remember_widths
from paths import CACHE_DIR

IMAGE_CACHE_DIR = CACHE_DIR / "item_images"

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

# Maps the raw 'type' field (the weapon slot a mod fits into) to a readable
# label for the Type dropdown. Mods with no type or '---' get bucketed
# together as "Other" since that's not a real category.
TYPE_DISPLAY_NAMES = {
    'WARFRAME': 'Warframe',
    'PRIMARY': 'Primary',
    'SECONDARY': 'Secondary',
    'MELEE': 'Melee',
    'SENTINEL': 'Sentinel',
    'STANCE': 'Stance',
    'ARCH-GUN': 'Arch-Gun',
    'ARCH-MELEE': 'Arch-Melee',
    'AURA': 'Aura',
    'PARAZON': 'Parazon',
    'KAVAT': 'Kavat',
    'KUBROW': 'Kubrow',
    'ARCHWING': 'Archwing',
    'HELMINTH CHARGER': 'Helminth Charger',
    'OTHER': 'Other',
}


def _type_bucket(raw_type):
    return raw_type if raw_type in TYPE_DISPLAY_NAMES else 'OTHER'


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

        header.addWidget(QLabel("Slot:"))
        self._type_combo = QComboBox()
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        header.addWidget(self._type_combo)

        header.addWidget(QLabel("Weapon/Type:"))
        self._source_combo = QComboBox()
        self._source_combo.currentIndexChanged.connect(self._filter)
        header.addWidget(self._source_combo)

        layout.addLayout(header)

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels([
            "Name", "Type", "Rarity", "Polarity", "Source", "Drop Location", "Owned"
        ])
        for col in range(7):
            self._table.horizontalHeader().setSectionResizeMode(col, QHeaderView.Interactive)
        apply_saved_widths(self._table, "mod_collection_table", [210, 110, 70, 80, 140, 320, 60])
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
        wfcd_names, wfcd_drops, wfcd_images = self._load_wfcd_data(base / 'wfcd_all_cache.json')
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
                'type_bucket': _type_bucket(mod_type),
                'rarity': rarity,
                'polarity': polarity,
                'source': source,
                'drop_location': drop_location,
                'owned': owned_count,
                'is_set': bool(set_name),
                'image_name': wfcd_images.get(unique, ''),
            })

        self._populate_type_combo()
        self._populate_table(self._mods)
        self._status.setText(f"Loaded {len(self._mods)} mods from ExportUpgrades")

    def _populate_type_combo(self):
        buckets = sorted(
            {m['type_bucket'] for m in self._mods},
            key=lambda b: TYPE_DISPLAY_NAMES.get(b, b)
        )
        self._type_combo.blockSignals(True)
        self._type_combo.clear()
        self._type_combo.addItem("All Slots", None)
        for bucket in buckets:
            self._type_combo.addItem(TYPE_DISPLAY_NAMES.get(bucket, bucket), bucket)
        self._type_combo.blockSignals(False)
        self._populate_source_combo(None)

    def _populate_source_combo(self, bucket):
        if bucket is None:
            sources = {m['source'] for m in self._mods if m['source']}
        else:
            sources = {m['source'] for m in self._mods if m['type_bucket'] == bucket and m['source']}
        self._source_combo.blockSignals(True)
        self._source_combo.clear()
        self._source_combo.addItem("All", None)
        for source in sorted(sources):
            self._source_combo.addItem(source, source)
        self._source_combo.blockSignals(False)

    def _on_type_changed(self, *_):
        bucket = self._type_combo.currentData()
        self._populate_source_combo(bucket)
        self._filter()

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
            return {}, {}, {}

        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get('items') or data.get('data') or []
        names = {}
        drops = {}
        images = {}
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
            if u and item.get('imageName'):
                images[u] = item['imageName']
        return names, drops, images

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
            _a0 = QTableWidgetItem(mod['name']); _a0.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            img_name = mod.get('image_name', '')
            if img_name:
                img_path = IMAGE_CACHE_DIR / img_name
                if img_path.exists():
                    pix = QPixmap(str(img_path))
                    if not pix.isNull():
                        _a0.setIcon(QIcon(pix.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
            self._table.setItem(r, 0, _a0)
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
        selected_bucket = self._type_combo.currentData()
        selected_source = self._source_combo.currentData()

        for r in range(self._table.rowCount()):
            name_item = self._table.item(r, 0)
            type_item = self._table.item(r, 1)
            source_item = self._table.item(r, 4)
            drop_item = self._table.item(r, 5)
            owned_item = self._table.item(r, 6)
            name = name_item.text().lower() if name_item else ''
            typ_raw = type_item.text() if type_item else ''
            typ = typ_raw.lower()
            source_raw = source_item.text() if source_item else ''
            source = source_raw.lower()
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
            if selected_bucket is not None and _type_bucket(typ_raw) != selected_bucket:
                visible = False
            if selected_source is not None and source_raw != selected_source:
                visible = False
            self._table.setRowHidden(r, not visible)

    def get_selected_mod(self):
        r = self._table.currentRow()
        if r < 0:
            return None
        return self._table.item(r, 0).text()
