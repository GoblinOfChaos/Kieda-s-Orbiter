#!/usr/bin/env python3
"""Modular Weapons tab: Zaw Strikes, Kitgun Chambers, Amp Prisms, MOA/Hound
Heads, K-Drive Decks, and Railjack Intrinsics.

Modular gear isn't tracked as a single inventory entry the way normal
weapons are - you build a Zaw/Kitgun/Amp/MOA/Hound/K-Drive from parts, and
only the specific mastery-granting part (Tip/Barrel/Prism/Head/Deck) is
what actually persists ownership history, via inventory.json's XPInfo list
(records XP per exact part uniqueName, present once you've ever owned that
part - even if the built weapon was later sold/dismantled).

Catalog + XPInfo-based ownership pattern verified against Cephalon Kronos's
inventoryParser.js (github.com/glowseeker/cephalon-kronos), which solved
this exact problem already. Rank/affinity math reuses the same quadratic
formula as MASTERY_HELPER_TAB.py (Zaw/Kitgun/Amp are regular weapons,
base 500; MOA/Hound/K-Drive are heavy categories, base 1000).

Railjack Intrinsics are structurally different - five fixed skill trees
(Tactical/Piloting/Engineering/Gunnery/Command) read directly from
inventory.json's PlayerSkills dict as a 0-10 rank, not a part catalog."""
import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QCheckBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox
)
from column_persistence import apply_saved_widths, remember_widths
from MASTERY_HELPER_TAB import _xp_to_rank, _max_xp_for

# Each category's catalog filter (matches a part's uniqueName in
# wfcd_all_cache.json) and the itype string MASTERY_HELPER_TAB's rank
# formula expects for that category.
CATEGORY_FILTERS = {
    'Zaw Strikes': (
        lambda un: '/Ostron/Melee/' in un and '/Tip' in un and 'PvP' not in un,
        'Zaw',
    ),
    'Kitgun Chambers': (
        lambda un: 'SUModularSecondarySet1/Barrel/' in un or 'InfKitGun/Barrels/' in un,
        'Kitgun',
    ),
    'Amp Prisms': (
        lambda un: ('OperatorAmplif' in un and 'barrel' in un.lower()) or 'drifterpistol' in un.lower(),
        'Amp',
    ),
    'MOA Heads': (
        lambda un: 'MoaPetParts/MoaPetHead' in un,
        'Moa',
    ),
    'Hound Heads': (
        lambda un: 'ZanukaPetParts/ZanukaPetPartHead' in un,
        'Hound',
    ),
    'K-Drive Decks': (
        lambda un: '/Hoverboard/' in un and 'Deck' in un,
        'K-Drive',
    ),
}

RAILJACK_INTRINSICS = [
    ('LPS_TACTICAL', 'Tactical'),
    ('LPS_PILOTING', 'Piloting'),
    ('LPS_ENGINEERING', 'Engineering'),
    ('LPS_GUNNERY', 'Gunnery'),
    ('LPS_COMMAND', 'Command'),
]

CATEGORIES = list(CATEGORY_FILTERS.keys()) + ['Railjack Intrinsics']


class ModularTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._items_by_category = {}
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(QLabel("Category:"))
        self._category_combo = QComboBox()
        self._category_combo.addItems(CATEGORIES)
        self._category_combo.currentIndexChanged.connect(self._on_category_changed)
        header.addWidget(self._category_combo)

        header.addWidget(QLabel("Search:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search...")
        self._search.textChanged.connect(self._filter)
        header.addWidget(self._search)

        self._hide_owned = QCheckBox("Hide owned")
        self._hide_owned.stateChanged.connect(self._filter)
        header.addWidget(self._hide_owned)

        layout.addLayout(header)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Name", "Rank", "Affinity", "Owned"])
        for col in range(4):
            self._table.horizontalHeader().setSectionResizeMode(col, QHeaderView.Interactive)
        apply_saved_widths(self._table, "modular_table", [220, 60, 140, 70])
        remember_widths(self._table, "modular_table")
        self._table.setSortingEnabled(True)
        self._table.verticalHeader().setVisible(False)
        self._table.sortByColumn(0, Qt.AscendingOrder)
        layout.addWidget(self._table)

        self._status = QLabel("")
        layout.addWidget(self._status)

    def _load(self):
        base = Path(__file__).parent
        inventory = self._load_json(base / 'inventory.json') or {}
        xp_map = {
            x['ItemType']: x.get('XP', 0)
            for x in inventory.get('XPInfo', [])
            if isinstance(x, dict) and x.get('ItemType')
        }

        wfcd = self._load_json(base / 'wfcd_all_cache.json') or []
        items = wfcd if isinstance(wfcd, list) else (wfcd.get('items') or wfcd.get('data') or [])

        for category, (matcher, itype) in CATEGORY_FILTERS.items():
            rows = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                uname = item.get('uniqueName', '')
                name = item.get('name', '')
                if not uname or not name or not matcher(uname):
                    continue
                xp = xp_map.get(uname, 0)
                rank = _xp_to_rank(xp, uname, itype)
                max_xp = _max_xp_for(uname, itype)
                rows.append({
                    'name': name,
                    'rank': rank,
                    'xp': xp,
                    'max_xp': max_xp,
                    'owned': xp > 0,
                })
            rows.sort(key=lambda r: r['name'])
            self._items_by_category[category] = rows

        player_skills = inventory.get('PlayerSkills', {}) or {}
        intrinsics_rows = []
        for key, label in RAILJACK_INTRINSICS:
            rank = player_skills.get(key, 0)
            intrinsics_rows.append({
                'name': label,
                'rank': rank,
                'xp': rank,
                'max_xp': 10,
                'owned': True,
            })
        self._items_by_category['Railjack Intrinsics'] = intrinsics_rows

        self._on_category_changed()

    def _load_json(self, path):
        try:
            with path.open() as fh:
                return json.load(fh)
        except Exception:
            return None

    def _on_category_changed(self, *_):
        category = self._category_combo.currentText()
        rows = self._items_by_category.get(category, [])
        self._populate_table(rows)
        owned = sum(1 for r in rows if r['owned'])
        self._status.setText(f"{category}: {owned}/{len(rows)} owned")

    def _populate_table(self, rows):
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        for row in rows:
            r = self._table.rowCount()
            self._table.insertRow(r)
            _a0 = QTableWidgetItem(row['name']); _a0.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter); self._table.setItem(r, 0, _a0)
            rank_item = QTableWidgetItem()
            rank_item.setData(Qt.DisplayRole, row['rank'])
            rank_item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            self._table.setItem(r, 1, rank_item)
            affinity_item = QTableWidgetItem(f"{row['xp']:,} / {row['max_xp']:,}")
            affinity_item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            self._table.setItem(r, 2, affinity_item)
            owned_item = QTableWidgetItem("Yes" if row['owned'] else "No")
            owned_item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            if row['owned']:
                owned_item.setForeground(Qt.cyan)
            self._table.setItem(r, 3, owned_item)
        self._table.setSortingEnabled(True)
        self._filter()

    def _filter(self, *_):
        q = self._search.text().strip().lower()
        hide_owned = self._hide_owned.isChecked()
        for r in range(self._table.rowCount()):
            name_item = self._table.item(r, 0)
            owned_item = self._table.item(r, 3)
            name = name_item.text().lower() if name_item else ''
            owned = owned_item.text() == 'Yes' if owned_item else False
            visible = True
            if q and q not in name:
                visible = False
            if hide_owned and owned:
                visible = False
            self._table.setRowHidden(r, not visible)
