#!/usr/bin/env python3
"""Relic Planner: three-panel UI to find relics matching a NEED list."""
import json
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QListWidget, QSplitter,
    QCheckBox,
)
from column_persistence import apply_saved_widths, remember_widths
from paths import DATA_DIR

BASE = Path(__file__).parent
ERAS = ["Lith", "Meso", "Neo", "Axi", "Vanguard"]
RARITY_FIELDS = ["rare1", "uncommon1", "uncommon2", "common1", "common2", "common3"]

class RelicPlannerTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_parts = []
        self._relics = {}
        self._need = []
        self._owned = {}        # part name → count
        self._owned_relics = {} # "Era Name" → {owned, vaulted, ...}
        self._crafted = set()   # parts ever built/mastered
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)

        # Left panel — part picker
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Prime Parts:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search parts...")
        self._search.textChanged.connect(self._filter_parts)
        left_layout.addWidget(self._search)
        self._part_list = QListWidget()
        self._part_list.itemDoubleClicked.connect(self._add_part)
        left_layout.addWidget(self._part_list)
        splitter.addWidget(left)

        # Middle panel — need list
        mid = QWidget()
        mid_layout = QVBoxLayout(mid)
        mid_layout.addWidget(QLabel("Need List:"))
        self._need_list = QListWidget()
        mid_layout.addWidget(self._need_list)
        btn_row = QHBoxLayout()
        self._remove_btn = QPushButton("Remove")
        self._remove_btn.clicked.connect(self._remove_part)
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self._clear_need)
        btn_row.addWidget(self._remove_btn)
        btn_row.addWidget(self._clear_btn)
        mid_layout.addLayout(btn_row)
        self._add_all_missing_btn = QPushButton("Add All Missing Parts")
        self._add_all_missing_btn.setToolTip(
            "Adds every prime part you currently own zero of.\n"
            "Includes parts you've crafted before and used up."
        )
        self._add_all_missing_btn.clicked.connect(self._add_all_missing)
        mid_layout.addWidget(self._add_all_missing_btn)

        self._add_unacquired_btn = QPushButton("Add Never Obtained")
        self._add_unacquired_btn.setToolTip(
            "Adds only parts you have never owned or crafted at all —\n"
            "excludes parts you built/mastered before and used up."
        )
        self._add_unacquired_btn.clicked.connect(self._add_unacquired)
        mid_layout.addWidget(self._add_unacquired_btn)
        splitter.addWidget(mid)

        # Right panel — relic matches
        right = QWidget()
        right_layout = QVBoxLayout(right)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Best Relics:"))
        filter_row.addStretch()
        self._owned_only_cb = QCheckBox("Show owned relics only")
        self._owned_only_cb.setToolTip(
            "When checked, only shows relics you currently own at least one of."
        )
        self._owned_only_cb.stateChanged.connect(self._compute)
        filter_row.addWidget(self._owned_only_cb)
        right_layout.addLayout(filter_row)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(["Relic", "Era", "Needed", "Owned", "Vaulted", "Needed Parts"])
        for col in range(6):
            self._table.horizontalHeader().setSectionResizeMode(col, QHeaderView.Interactive)
        apply_saved_widths(self._table, "relic_planner_table", [160, 70, 60, 60, 65, 280])
        remember_widths(self._table, "relic_planner_table")
        self._table.setSortingEnabled(True)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.itemSelectionChanged.connect(self._on_relic_selection_changed)
        right_layout.addWidget(self._table)
        self._status = QLabel("")
        right_layout.addWidget(self._status)
        splitter.addWidget(right)

        splitter.setSizes([300, 250, 500])
        root.addWidget(splitter)

    def _load(self):
        try:
            filt = json.loads((BASE / "filtered_items.json").read_text())
            self._relics = filt.get("relics") or {}
            parts = set()
            for eq in filt.get("eqmt", {}).values():
                for pname in eq.get("parts", {}).keys():
                    parts.add(pname)
            self._all_parts = sorted(parts)
            self._filter_parts("")
        except Exception as e:
            self._status.setText(f"Load error: {e}")
        try:
            self._owned = json.loads((BASE / "owned_items.json").read_text())
        except Exception:
            self._owned = {}
        try:
            self._crafted = set(json.loads((DATA_DIR / "crafted_parts.json").read_text()))
        except Exception:
            self._crafted = set()
        try:
            raw = json.loads((BASE / "owned_relics.json").read_text())
            # Key format in owned_relics.json is "Era Name" e.g. "Axi A1"
            self._owned_relics = raw
        except Exception:
            self._owned_relics = {}

    def _filter_parts(self, text):
        q = text.strip().lower()
        self._part_list.clear()
        for p in self._all_parts:
            if not q or q in p.lower():
                self._part_list.addItem(p)

    def _add_part(self, item):
        part = item.text()
        if part not in self._need:
            self._need.append(part)
            self._need_list.addItem(part)
            self._compute()

    def _remove_part(self):
        row = self._need_list.currentRow()
        if row >= 0:
            self._need.pop(row)
            self._need_list.takeItem(row)
            self._compute()

    def _clear_need(self):
        self._need.clear()
        self._need_list.clear()
        self._compute()

    def _add_all_missing(self):
        """Add every part currently at zero count (includes previously crafted)."""
        added = 0
        for part in self._all_parts:
            if self._owned.get(part, 0) == 0 and part not in self._need:
                self._need.append(part)
                self._need_list.addItem(part)
                added += 1
        if added:
            self._compute()
        self._status.setText(f"Added {added} missing part(s) to the need list.")

    def _add_unacquired(self):
        """Add only parts never obtained at all — not in inventory AND never crafted."""
        added = 0
        for part in self._all_parts:
            never_owned   = self._owned.get(part, 0) == 0
            never_crafted = part not in self._crafted
            if never_owned and never_crafted and part not in self._need:
                self._need.append(part)
                self._need_list.addItem(part)
                added += 1
        if added:
            self._compute()
        self._status.setText(
            f"Added {added} never-obtained part(s) "
            f"(excludes {len(self._crafted)} previously crafted parts)."
        )

    def _compute(self):
        if not self._need:
            self._table.setRowCount(0)
            self._status.setText("Add parts to your need list.")
            return

        owned_only = self._owned_only_cb.isChecked()
        need_set = set(p.lower() for p in self._need)
        results = []
        for era in ERAS:
            for rname, relic in self._relics.get(era, {}).items():
                key = f"{era} {rname}"
                relic_info = self._owned_relics.get(key, {})
                owned_count = relic_info.get("owned", 0)
                vaulted = relic_info.get("vaulted", False)

                if owned_only and owned_count == 0:
                    continue

                matches = []
                for field in RARITY_FIELDS:
                    part = relic.get(field, "")
                    if part and part.lower() in need_set:
                        matches.append(part)
                if matches:
                    results.append((era, rname, len(matches), matches, owned_count, vaulted))

        # Sort: owned first, then by match count
        results.sort(key=lambda r: (-r[4], -r[2]))

        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(results))
        for i, (era, rname, count, matches, owned_count, vaulted) in enumerate(results):
            key = f"{era} {rname}"
            name_item = QTableWidgetItem(key)
            name_item.setData(Qt.UserRole, matches)
            self._table.setItem(i, 0, name_item)
            self._table.setItem(i, 1, QTableWidgetItem(era))

            cnt = QTableWidgetItem()
            cnt.setData(Qt.DisplayRole, count)
            self._table.setItem(i, 2, cnt)

            own_item = QTableWidgetItem()
            own_item.setData(Qt.DisplayRole, owned_count)
            self._table.setItem(i, 3, own_item)

            vault_item = QTableWidgetItem("Yes" if vaulted else "No")
            self._table.setItem(i, 4, vault_item)

            self._table.setItem(i, 5, QTableWidgetItem(""))

            # Colour rows: bright if owned, dim if not, red-tinted if vaulted+unowned
            if owned_count > 0:
                row_color = QColor("#0f2e18")   # dark green tint — you have it
            elif vaulted:
                row_color = QColor("#2e1010")   # dark red tint — vaulted, can't get
            else:
                row_color = QColor("#1a1e2e")   # normal dark — unvaulted but unowned
            for col in range(6):
                item = self._table.item(i, col)
                if item:
                    item.setBackground(row_color)

        self._table.setSortingEnabled(True)
        owned_shown = sum(1 for r in results if r[4] > 0)
        self._status.setText(
            f"{len(results)} relics match  ·  "
            f"{owned_shown} owned  ·  "
            f"{len(results) - owned_shown} not owned"
        )

    def _on_relic_selection_changed(self):
        row = self._table.currentRow()
        if row >= 0:
            self._on_relic_row_clicked(row, 0)

    def _on_relic_row_clicked(self, row, col):
        name_item = self._table.item(row, 0)
        if not name_item:
            return
        matches = name_item.data(Qt.UserRole) or []
        self._table.setItem(row, 3, QTableWidgetItem(", ".join(matches)))
