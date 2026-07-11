#!/usr/bin/env python3
"""Kieda's Orbiter — Warframe companion app."""

import json
import sys
from collections import defaultdict
from pathlib import Path

import sys as _wfi_sys
from pathlib import Path as _WfiPath
_wfi_sys.path.insert(0, str(_WfiPath(__file__).parent))
from theme import WFINFO_STYLESHEET, get_theme, load_theme, save_theme, THEMES, THEME_DESCRIPTIONS, get_palette
from column_persistence import apply_saved_widths, remember_widths

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QIcon
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QTabWidget, QDialog, QProgressBar, QPushButton,
)
from paths import DATA_DIR, WFINFO_DIR

WFINFO_ICON = str(Path.home() / ".local/share/icons/hicolor/scalable/apps/orbiter.svg")

HOME = Path.home()
OWNED_FILE = WFINFO_DIR / "owned_items.json"
ITEMS_FILE = WFINFO_DIR / "filtered_items.json"
PRICES_FILE = WFINFO_DIR / "prices.json"
INVENTORY_FILE = WFINFO_DIR / "inventory.json"
WFCD_CACHE = WFINFO_DIR / "wfcd_all_cache.json"
CRAFTED_FILE = DATA_DIR / "crafted-before.json"
OWNED_RELICS_FILE = WFINFO_DIR / "owned_relics.json"

ERAS = ["Lith", "Meso", "Neo", "Axi", "Vanguard"]
RARITY_FIELDS = {
    "rare1": "Rare",
    "uncommon1": "Uncommon", "uncommon2": "Uncommon",
    "common1": "Common", "common2": "Common", "common3": "Common",
}
RARITY_COLORS = {"Rare": "#d4af37", "Uncommon": "#67d164", "Common": "#aaaaaa"}
INTACT_CHANCES = {"Rare": 0.0203, "Uncommon": 0.1100, "Common": 0.2533}


def _lookup_with_bp(d, part):
    """Look up part in dict, trying with/without ' Blueprint' suffix."""
    if part in d:
        return d[part]
    if part.endswith(" Blueprint"):
        s = part[:-len(" Blueprint")]
        if s in d:
            return d[s]
    elif (part + " Blueprint") in d:
        return d[part + " Blueprint"]
    return None


def _owned_count(owned, part):
    """Return count of a part owned; handles ' Blueprint' suffix mismatch."""
    v = _lookup_with_bp(owned, part)
    if isinstance(v, int):
        return v
    if isinstance(v, dict):
        return v.get("count", 0)
    return 0


class RelicPopup(QDialog):
    def __init__(self, parent, era, relic_name, relic, prices, ducats, owned, crafted, auto_crafted):
        super().__init__(parent)
        vault = " [VAULTED]" if relic.get("vaulted") else ""
        self.setWindowTitle(f"{era} {relic_name}{vault}")
        self.resize(720, 400)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<h2>{era} {relic_name}{vault}</h2>"))

        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Rarity", "Part", "Status", "Plat", "Ducats"])
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        h = table.horizontalHeader()
        for col in range(5):
            h.setSectionResizeMode(col, QHeaderView.Interactive)

        rows = []
        for field, rarity in RARITY_FIELDS.items():
            part = relic.get(field)
            if not part:
                continue
            cnt = _owned_count(owned, part)
            if cnt > 0:
                status, status_color = f"OWNED x{cnt}", "#888"
            elif part in crafted or part in auto_crafted or (part + " Blueprint") in auto_crafted:
                status, status_color = "CRAFTED", "#a3d4ff"
            else:
                status, status_color = "NEED", "#3eff3e"
            plat = prices.get(part, prices.get(part + " Blueprint", 0))
            duc = ducats.get(part, ducats.get(part + " Blueprint", 0))
            rows.append((rarity, part, status, status_color, plat, duc))

        rarity_order = {"Rare": 0, "Uncommon": 1, "Common": 2}
        rows.sort(key=lambda r: rarity_order.get(r[0], 9))

        table.setRowCount(len(rows))
        ev_total = ev_need = 0.0
        for i, (rarity, part, status, status_color, plat, duc) in enumerate(rows):
            it = QTableWidgetItem(rarity)
            it.setForeground(QBrush(QColor(RARITY_COLORS[rarity])))
            table.setItem(i, 0, it)
            table.setItem(i, 1, QTableWidgetItem(part))
            si = QTableWidgetItem(status)
            si.setForeground(QBrush(QColor(status_color)))
            table.setItem(i, 2, si)
            pi = QTableWidgetItem(f"{plat:.1f}" if plat else "")
            pi.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(i, 3, pi)
            di = QTableWidgetItem(str(duc) if duc else "")
            di.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(i, 4, di)
            ev = INTACT_CHANCES[rarity] * (plat or 0)
            ev_total += ev
            if status == "NEED":
                ev_need += ev
        layout.addWidget(table)
        apply_saved_widths(table, "relic_popup_table", [80, 220, 90, 70, 70])
        remember_widths(table, "relic_popup_table")
        layout.addWidget(QLabel(
            f"Expected value (Intact solo): <b>{ev_total:.2f}p</b> per opening "
            f"&nbsp;|&nbsp; For YOUR NEEDs only: <b>{ev_need:.2f}p</b>"
        ))


class Tracker(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kieda's Orbiter")
        self.setMinimumSize(1100, 700)
        from PySide6.QtCore import QSettings
        self._settings = QSettings("kiedas-orbiter", "MainWindow")
        saved = self._settings.value("geometry")
        restored_ok = bool(saved) and self.restoreGeometry(saved)
        if restored_ok:
            # Saved geometry can come from a completely different screen
            # (different machine/resolution) — if it no longer fits any
            # available screen, fall back to a sane default instead of
            # leaving the window mis-sized or partially off-screen.
            screen = self.screen() or QApplication.primaryScreen()
            avail = screen.availableGeometry()
            frame = self.frameGeometry()
            fits = avail.intersected(frame).width() >= frame.width() * 0.5 and \
                   avail.intersected(frame).height() >= frame.height() * 0.5
            if not fits:
                restored_ok = False
        if not restored_ok:
            screen = QApplication.primaryScreen()
            avail = screen.availableGeometry() if screen else None
            width, height = 1400, 900
            if avail:
                width = min(width, avail.width())
                height = min(height, avail.height())
            self.resize(width, height)
            if avail:
                self.move(avail.center().x() - width // 2, avail.center().y() - height // 2)

        try:
            self.items_data = json.loads(ITEMS_FILE.read_text())
        except Exception:
            # First launch, or install.py's data download never completed —
            # try to self-heal by fetching it now instead of hard-failing.
            try:
                from update_manager import quick_update
                quick_update()
                self.items_data = json.loads(ITEMS_FILE.read_text())
            except Exception as e:
                QMessageBox.critical(
                    self, "Load failed",
                    f"Couldn't load or download Warframe item data "
                    f"(filtered_items.json): {e}\n\n"
                    f"Check your internet connection, then try again, or run "
                    f"update.py manually."
                )
                QApplication.quit()
                return
        try:
            self.owned = json.loads(OWNED_FILE.read_text())
        except (OSError, json.JSONDecodeError):
            # No inventory synced yet (fresh install, or Warframe hasn't been
            # launched with the helper running) — treat as owning nothing.
            self.owned = {}
        try:
            self.crafted = set(json.loads(CRAFTED_FILE.read_text()))
        except (OSError, json.JSONDecodeError):
            self.crafted = set()
        try:
            price_list = json.loads(PRICES_FILE.read_text())
            self.prices = {}
            for it in price_list:
                if isinstance(it, dict) and "name" in it:
                    try:
                        self.prices[it["name"]] = float(it.get("custom_avg") or 0)
                    except (TypeError, ValueError):
                        self.prices[it["name"]] = 0.0
        except (OSError, json.JSONDecodeError, KeyError):
            self.prices = {}
        try:
            self.owned_relics = json.loads(OWNED_RELICS_FILE.read_text())
        except (OSError, json.JSONDecodeError):
            self.owned_relics = {}

        self._build_indices()
        self.auto_crafted = self._auto_detect_crafted()
        self._build_all_rows()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Title bar ─────────────────────────────────────────────────────
        self._title_bar = QWidget()
        self._title_bar.setFixedHeight(44)
        tb_layout = QHBoxLayout(self._title_bar)
        tb_layout.setContentsMargins(16, 0, 16, 0)
        self._app_lbl = QLabel("⬡  Kieda's Orbiter")
        tb_layout.addWidget(self._app_lbl)
        tb_layout.addStretch()
        layout.addWidget(self._title_bar)

        # ── Body: sidebar + content ────────────────────────────────────────
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # ── Left sidebar ───────────────────────────────────────────────────
        from PySide6.QtWidgets import QStackedWidget, QScrollArea, QSizePolicy
        self._sidebar = QWidget()
        self._sidebar.setFixedWidth(210)
        sidebar_layout = QVBoxLayout(self._sidebar)
        sidebar_layout.setContentsMargins(0, 8, 0, 8)
        sidebar_layout.setSpacing(0)

        # ── Content stack ──────────────────────────────────────────────────
        self._stack = QStackedWidget()
        stack = self._stack

        self._nav_buttons = []
        self._current_nav_idx = [0]

        self._section_labels = []
        self._nav_btn_list = []

        def _add_section(label):
            lbl = QLabel(label.upper())
            self._section_labels.append(lbl)
            sidebar_layout.addWidget(lbl)

        def _add_page(label, widget_factory, icon=""):
            idx = stack.count()
            # Lazy-load: insert placeholder, build on first visit
            placeholder = QWidget()
            placeholder._factory = widget_factory
            placeholder._built = False
            stack.addWidget(placeholder)

            btn_text = f"{icon} {label}" if icon else label
            btn = QPushButton(btn_text)
            btn.setCheckable(True)
            btn.setAutoExclusive(False)
            btn.setFlat(True)
            self._nav_btn_list.append(btn)

            def _on_click(checked, _idx=idx, _btn=btn):
                # Deselect all others
                for b in self._nav_buttons:
                    b.setChecked(False)
                _btn.setChecked(True)
                # Lazy-build if needed
                page = stack.widget(_idx)
                if hasattr(page, '_built') and not page._built:
                    try:
                        real = page._factory()
                    except Exception:
                        import traceback; traceback.print_exc()
                        real = QLabel("Failed to load")
                    stack.removeWidget(page)
                    stack.insertWidget(_idx, real)
                    page.deleteLater()
                stack.setCurrentIndex(_idx)

            btn.clicked.connect(_on_click)
            self._nav_buttons.append(btn)
            sidebar_layout.addWidget(btn)
            return btn

        # ── Dashboard section ──────────────────────────────────────────────
        _add_section("World State")
        _add_page("Dashboard",         lambda: __import__('DASHBOARD_TAB',     fromlist=['DashboardTab']).DashboardTab(),        "◎")

        # ── Inventory section ──────────────────────────────────────────────
        _add_section("Inventory")
        _add_page("Inventory",        lambda: __import__('INVENTORY_TAB',    fromlist=['InventoryTab']).InventoryTab(),       "○")
        _add_page("Foundry",          lambda: __import__('FOUNDRY_TAB',      fromlist=['FoundryTab']).FoundryTab(),           "⚒")
        _add_page("Missing Parts",    lambda: self._build_parts_tab(),                                                        "□")
        _add_page("Set Progress",     lambda: self._build_sets_tab(),                                                         "▣")
        _add_page("Mod Collection",   lambda: __import__('MOD_COLLECTION_TAB', fromlist=['ModCollectionTab']).ModCollectionTab(), "▽")
        _add_page("Mastery Helper",   lambda: __import__('MASTERY_HELPER_TAB',fromlist=['MasteryHelperTab']).MasteryHelperTab(),"★")

        # ── Relics section ─────────────────────────────────────────────────
        _add_section("Relics")
        _add_page("Relic Planner",    lambda: __import__('RELIC_PLANNER_TAB', fromlist=['RelicPlannerTab']).RelicPlannerTab(), "�")
        _add_page("Best Relics",      lambda: self._build_relics_tab(),                                                        "\u25c6")

        # ── Rivens section ──────────────────────────────────────────────
        _add_section("Rivens")
        _add_page("Riven Grader",     lambda: __import__('RIVEN_GRADER_TAB',  fromlist=['RivenGraderTab']).RivenGraderTab(),  "\u2736")

        # ── Market section ─────────────────────────────────────────────────
        _add_section("Market")
        _add_page("Market",           lambda: __import__('MARKET_TAB',        fromlist=['MarketTab']).MarketTab(),            "◈")
        _add_page("Stats History",    lambda: __import__('STATS_HISTORY_TAB', fromlist=['StatsHistoryTab']).StatsHistoryTab(),"▴")

        # ── Equipment section ──────────────────────────────────────────────
        # Pre-load equipment data once, then build each tab individually on demand
        _add_section("Equipment")
        _eq_icons = {
            "Warframe": "\u25a0", "Primary": "\u2299", "Secondary": "\u25cb",
            "Melee": "\u2020", "Archwing": "\u25b3", "Necramech": "\u25a3",
            "Sentinel": "\u25c7", "Sentinel Weapon": "\u2694", "Pet": "\u25b6",
        }
        for eq_name in ["Warframe","Primary","Secondary","Melee","Archwing",
                        "Necramech","Sentinel","Sentinel Weapon","Pet"]:
            def _eq_factory(name=eq_name):
                # Build only the requested tab — load data once, build one tab
                from equipment_tabs import EquipmentTabBuilder
                import PySide6.QtWidgets as _w
                builder = EquipmentTabBuilder(_w.QTabWidget())
                if not builder.reload_data():
                    return _w.QLabel(f"No equipment data yet — refresh inventory first")
                return builder._build_tab(name, builder.data.get(name, []))
            _add_page(eq_name, _eq_factory, _eq_icons.get(eq_name, ""))

        # ── System section ─────────────────────────────────────────────────
        _add_section("System")
        _add_page("Status & Tools",   lambda: __import__('STATUS_TAB',       fromlist=['StatusTab']).StatusTab(),            "\u2699")
        _add_page("Credits",          lambda: __import__('CREDITS_TAB',      fromlist=['CreditsTab']).CreditsTab(),          "\u2665")

        sidebar_layout.addStretch()

        body_layout.addWidget(self._sidebar)
        body_layout.addWidget(stack, stretch=1)
        layout.addWidget(body, stretch=1)

        self._apply_chrome_styles()

        # Select first page by default
        if self._nav_buttons:
            self._nav_buttons[0].click()

    def _apply_chrome_styles(self):
        """Apply/re-apply theme colors to the main window chrome (title bar, sidebar, nav)."""
        p = get_palette()
        self._title_bar.setStyleSheet(
            f"background: {p['bg_header']}; border-bottom: 2px solid {p['accent_mid']};"
        )
        self._app_lbl.setStyleSheet(
            f"color: {p['gold']}; font-size: 15px; font-weight: 700; "
            f"letter-spacing: 1px; background: transparent;"
        )
        self._sidebar.setStyleSheet(
            f"background: {p['bg_header']}; border-right: 1px solid {p['border']};"
        )
        self._stack.setStyleSheet(f"background: {p['bg']};")
        for lbl in self._section_labels:
            lbl.setStyleSheet(
                f"color: {p['gold_bright']}; font-size: 10px; font-weight: 700; "
                f"letter-spacing: 0.5px; padding: 12px 12px 4px 12px; "
                f"background: transparent;"
            )
        for btn in self._nav_btn_list:
            btn.setStyleSheet(
                f"QPushButton {{ text-align: left; padding: 7px 8px 7px 14px; "
                f"color: {p['fg_dim']}; background: transparent; border: none; "
                f"font-size: 12px; border-left: 3px solid transparent; }}"
                f"QPushButton:hover {{ color: {p['fg']}; background: {p['bg_card']}; "
                f"border-left: 3px solid {p['accent_mid']}; }}"
                f"QPushButton:checked {{ color: {p['gold_bright']}; background: {p['bg_card']}; "
                f"border-left: 3px solid {p['accent']}; font-weight: 600; }}"
            )

    def _build_indices(self):
        self.part_to_relics = defaultdict(list)
        for era in ERAS:
            era_data = self.items_data.get("relics", {}).get(era, {})
            for rname, relic in era_data.items():
                vaulted = bool(relic.get("vaulted", False))
                for field, rarity in RARITY_FIELDS.items():
                    p = relic.get(field)
                    if p:
                        self.part_to_relics[p].append((era, rname, rarity, vaulted))
        self.part_to_eq = {}
        self.part_ducats = {}
        self.eq_info = {}
        for eq_name, eq in self.items_data.get("eqmt", {}).items():
            self.eq_info[eq_name] = {"type": eq.get("type", "?"), "vaulted": bool(eq.get("vaulted", False))}
            for pname, pdata in eq.get("parts", {}).items():
                self.part_to_eq[pname] = eq_name
                self.part_ducats[pname] = pdata.get("ducats", 0) if isinstance(pdata, dict) else 0

    def _auto_detect_crafted(self):
        auto = {}
        try:
            inv = json.loads(INVENTORY_FILE.read_text())
        except (OSError, json.JSONDecodeError):
            return auto
        try:
            wfcd = json.loads(WFCD_CACHE.read_text())
        except (OSError, json.JSONDecodeError):
            return auto
        path_to_name = {}
        items_list = wfcd if isinstance(wfcd, list) else (wfcd.get("items", []) if isinstance(wfcd, dict) else [])
        for item in items_list:
            if isinstance(item, dict):
                u, n = item.get("uniqueName"), item.get("name")
                if u and n:
                    path_to_name[u] = n
        paths = set()
        for cat in ["Suits", "LongGuns", "Pistols", "Melee", "SpaceSuits", "SpaceGuns", "SpaceMelee", "Sentinels", "SentinelWeapons", "MechSuits"]:
            for it in inv.get(cat, []) or []:
                if isinstance(it, dict):
                    p = it.get("ItemType")
                    if p:
                        paths.add(p)
        for it in inv.get("XPInfo", []) or []:
            if isinstance(it, dict):
                p = it.get("ItemType")
                # FIX: presence of XPInfo entry = mastered (XP resets to 0 when sold)
                if p:
                    paths.add(p)
        eq_names = set()
        for p in paths:
            n = path_to_name.get(p)
            if n and "Prime" in n:
                eq_names.add(n)
        for eq_name in eq_names:
            eq = self.items_data.get("eqmt", {}).get(eq_name)
            if not eq:
                continue
            for pname in eq.get("parts", {}).keys():
                auto[pname] = eq_name
                if not pname.endswith(" Blueprint"):
                    auto[pname + " Blueprint"] = eq_name
        return auto

    def _build_all_rows(self):
        self.all_rows = []
        for part, info in self.owned.items():
            cnt = info if isinstance(info, int) else 0
            if cnt != 0:
                continue
            eq = self.part_to_eq.get(part)
            relics = list(self.part_to_relics.get(part, []))
            if (not eq or not relics) and part.endswith(" Blueprint"):
                s = part[:-len(" Blueprint")]
                if not eq:
                    eq = self.part_to_eq.get(s)
                if not relics:
                    relics = list(self.part_to_relics.get(s, []))
            eq = eq or "(unknown)"
            meta = self.eq_info.get(eq, {"type": "?", "vaulted": False})
            plat = self.prices.get(part, self.prices.get(part[:-len(" Blueprint")] if part.endswith(" Blueprint") else (part + " Blueprint"), 0))
            ducats = self.part_ducats.get(part, self.part_ducats.get(part[:-len(" Blueprint")] if part.endswith(" Blueprint") else (part + " Blueprint"), 0))
            self.all_rows.append({"equipment": eq, "type": meta["type"], "eq_vaulted": meta["vaulted"], "part": part, "relics": relics, "plat": plat, "ducats": ducats})
        self.all_rows.sort(key=lambda r: (r["equipment"], r["part"]))

    # ============ Missing Parts tab ============
    def _build_parts_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        fr = QHBoxLayout()
        fr.addWidget(QLabel("Search:"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Octavia, Forma, Barrel...")
        self.search.textChanged.connect(self.refresh_parts)
        fr.addWidget(self.search, stretch=1)
        fr.addWidget(QLabel("Era:"))
        self.era_combo = QComboBox()
        self.era_combo.addItems(["Any"] + ERAS)
        self.era_combo.currentTextChanged.connect(self.refresh_parts)
        fr.addWidget(self.era_combo)
        fr.addWidget(QLabel("Type:"))
        self.type_combo = QComboBox()
        types = sorted({r["type"] for r in self.all_rows})
        self.type_combo.addItems(["Any"] + types)
        self.type_combo.currentTextChanged.connect(self.refresh_parts)
        fr.addWidget(self.type_combo)
        fr.addWidget(QLabel("Relics:"))
        self.vault_combo = QComboBox()
        self.vault_combo.addItems(["All", "Non-vaulted only"])
        self.vault_combo.currentTextChanged.connect(self.refresh_parts)
        fr.addWidget(self.vault_combo)
        self.hide_crafted = QCheckBox("Hide crafted-before")
        self.hide_crafted.stateChanged.connect(self.refresh_parts)
        fr.addWidget(self.hide_crafted)
        self.have_relics_only = QCheckBox("Have relics only")
        self.have_relics_only.stateChanged.connect(self.refresh_parts)
        fr.addWidget(self.have_relics_only)
        layout.addLayout(fr)

        self.parts_summary = QLabel()
        layout.addWidget(self.parts_summary)
        self.parts_table = QTableWidget()
        self.parts_table.setColumnCount(9)
        self.parts_table.setHorizontalHeaderLabels(["Equipment", "Type", "V", "Part (NEED)", "Plat", "Ducats", "Crafted", "Have?", "Drops From"])
        self.parts_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.parts_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.parts_table.setAlternatingRowColors(True)
        self.parts_table.verticalHeader().setVisible(False)
        h = self.parts_table.horizontalHeader()
        for c in range(9):
            h.setSectionResizeMode(c, QHeaderView.Interactive)
        self.parts_table.itemChanged.connect(self._on_item_changed)
        self.parts_table.cellClicked.connect(self._on_part_cell_clicked)
        layout.addWidget(self.parts_table)
        apply_saved_widths(self.parts_table, "parts_table", [180, 90, 40, 200, 60, 70, 70, 60, 260])
        remember_widths(self.parts_table, "parts_table")
        legend = QLabel(
            'Relic ownership: '
            '<span style="color: #4CAF50;">● Owned</span> &nbsp; '
            '<span style="color: #FFC107;">● Farmable</span> &nbsp; '
            '<span style="color: #F44336;">● Vaulted (need)</span>'
            ' &nbsp; &nbsp; Rarity: '
            '<span style="color: #d4af37;">(R)</span> '
            '<span style="color: #67d164;">(U)</span> '
            '<span style="color: #aaaaaa;">(C)</span>'
            ' &nbsp; &nbsp; <b>V</b> = equipment vaulted &nbsp; '
            '<i>[V]</i>=relic vaulted'
        )
        legend.setStyleSheet("padding: 6px; color: #ccc;")
        layout.addWidget(legend)
        self.refresh_parts()
        return w

    def _relic_status(self, era, name, vaulted_fallback):
        """Return (owned_count, color_hex, kind) for a relic.
        kind: 'owned' | 'farmable' | 'vaulted'."""
        info = self.owned_relics.get(f"{era} {name}", {})
        owned = info.get("owned", 0)
        vaulted = info.get("vaulted", vaulted_fallback)
        if owned > 0:
            return owned, "#4CAF50", "owned"
        if vaulted:
            return 0, "#F44336", "vaulted"
        return 0, "#FFC107", "farmable"

    def refresh_parts(self):
        q = self.search.text().lower()
        era_f = self.era_combo.currentText()
        type_f = self.type_combo.currentText()
        non_vaulted = self.vault_combo.currentIndex() == 1
        filtered = []
        for r in self.all_rows:
            if q and q not in r["part"].lower() and q not in r["equipment"].lower():
                continue
            if type_f != "Any" and r["type"] != type_f:
                continue
            if self.hide_crafted.isChecked() and (r["part"] in self.crafted or r["part"] in self.auto_crafted):
                continue
            if self.have_relics_only.isChecked():
                has_any = any(
                    self.owned_relics.get(f"{era} {nm}", {}).get("owned", 0) > 0
                    for era, nm, _, _ in r["relics"]
                )
                if not has_any:
                    continue
            relics = r["relics"]
            if era_f != "Any":
                relics = [x for x in relics if x[0] == era_f]
            if non_vaulted:
                relics = [x for x in relics if not x[3]]
            if (era_f != "Any" or non_vaulted) and not relics:
                continue
            filtered.append((r, relics))

        self.parts_table.blockSignals(True)
        self.parts_table.setRowCount(len(filtered))
        self._row_to_part = {}
        self._row_to_relics = {}
        for i, (r, relics) in enumerate(filtered):
            _pt0 = QTableWidgetItem(r["equipment"])
            _pt0.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.parts_table.setItem(i, 0, _pt0)
            _pt1 = QTableWidgetItem(r["type"]); _pt1.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            self.parts_table.setItem(i, 1, _pt1)
            v = QTableWidgetItem("V" if r["eq_vaulted"] else "")
            v.setForeground(QBrush(QColor("#888")))
            v.setTextAlignment(Qt.AlignCenter)
            self.parts_table.setItem(i, 2, v)
            part_item = QTableWidgetItem(r["part"])
            part_item.setToolTip("Click to see which relics drop this part")
            self.parts_table.setItem(i, 3, part_item)
            self._row_to_relics[i] = r["relics"]
            pi = QTableWidgetItem(f"{r['plat']:.1f}" if r["plat"] else "")
            pi.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.parts_table.setItem(i, 4, pi)
            di = QTableWidgetItem(str(r["ducats"]) if r["ducats"] else "")
            di.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.parts_table.setItem(i, 5, di)
            chk = QTableWidgetItem()
            chk.setTextAlignment(Qt.AlignCenter)
            ae = self.auto_crafted.get(r["part"])
            if ae:
                chk.setFlags(Qt.ItemIsEnabled)
                chk.setCheckState(Qt.Checked)
                chk.setToolTip(f"Auto-detected: you own or have mastered {ae}")
                chk.setForeground(QBrush(QColor("#888")))
            else:
                chk.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                chk.setCheckState(Qt.Checked if (r["part"] in self.crafted or r["part"] in self.auto_crafted) else Qt.Unchecked)
                if r["part"] in self.crafted:
                    chk.setToolTip("Manually marked as crafted")
            self.parts_table.setItem(i, 6, chk)
            self._row_to_part[i] = r["part"]
            # Have? column - any owned relic that drops this part?
            has_owned_relic = any(
                self.owned_relics.get(f"{era} {nm}", {}).get("owned", 0) > 0
                for era, nm, _, _ in r["relics"]
            )
            have_item = QTableWidgetItem("✓" if has_owned_relic else "")
            have_item.setTextAlignment(Qt.AlignCenter)
            if has_owned_relic:
                have_item.setForeground(QBrush(QColor("#4CAF50")))
            self.parts_table.setItem(i, 7, have_item)

            if relics:
                items = []
                for era, name, rarity, vlt in relics:
                    owned, own_color, _ = self._relic_status(era, name, vlt)
                    rarity_color = RARITY_COLORS.get(rarity, "#fff")
                    own_suffix = f" x{owned}" if owned > 0 else ""
                    vmark = " [V]" if vlt else ""
                    items.append(
                        f'<a href="{era}|{name}" style="text-decoration: none;">'
                        f'<span style="color: {own_color}; font-weight: 500;">'
                        f'{era} {name}{own_suffix}{vmark}</span>'
                        f'<span style="color: {rarity_color};"> ({rarity[0]})</span>'
                        f'</a>'
                    )
                lbl = QLabel(" &middot; ".join(items))
                lbl.linkActivated.connect(self._on_relic_link)
            else:
                lbl = QLabel('<span style="color:#666;">(no relic source)</span>')
            lbl.setTextFormat(Qt.RichText)
            lbl.setStyleSheet("padding: 4px;")
            lbl.setWordWrap(True)
            lbl.setOpenExternalLinks(False)
            self.parts_table.setCellWidget(i, 8, lbl)
            self.parts_table.resizeRowToContents(i)
        self.parts_table.blockSignals(False)

        auto_in_need = sum(1 for r in self.all_rows if r["part"] in self.auto_crafted)
        self.parts_summary.setText(
            f"Showing {len(filtered)} of {len(self.all_rows)} NEED parts "
            f"({auto_in_need} auto-detected as crafted, {len(self.crafted)} manually marked)"
        )

    def _on_item_changed(self, item):
        if item.column() != 6:
            return
        part = self._row_to_part.get(item.row())
        if part is None:
            return
        if item.checkState() == Qt.Checked:
            self.crafted.add(part)
        else:
            self.crafted.discard(part)
        self._save_crafted()
        if self.hide_crafted.isChecked():
            self.refresh_parts()

    def _save_crafted(self):
        try:
            CRAFTED_FILE.parent.mkdir(parents=True, exist_ok=True)
            CRAFTED_FILE.write_text(json.dumps(sorted(self.crafted)))
        except OSError:
            pass

    def _on_relic_link(self, link):
        try:
            era, name = link.split("|", 1)
        except ValueError:
            return
        self._show_relic(era, name)

    def _show_relic(self, era, name):
        relic = self.items_data.get("relics", {}).get(era, {}).get(name)
        if not relic:
            return
        RelicPopup(self, era, name, relic, self.prices, self.part_ducats, self.owned, self.crafted, self.auto_crafted).exec()

    def _on_part_cell_clicked(self, row, col):
        if col != 3:
            return
        part = self._row_to_part.get(row)
        if not part:
            return
        self._show_part_relics(part, self._row_to_relics.get(row, []))

    def _show_part_relics(self, part, relics):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Relics dropping: {part}")
        dlg.resize(480, 320)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(f"<h3>{part}</h3>"))
        if not relics:
            layout.addWidget(QLabel('<span style="color:#666;">No relic source found for this part.</span>'))
        else:
            items = []
            for era, name, rarity, vlt in relics:
                owned, own_color, _ = self._relic_status(era, name, vlt)
                rarity_color = RARITY_COLORS.get(rarity, "#fff")
                own_suffix = f" x{owned}" if owned > 0 else ""
                vmark = " [V]" if vlt else ""
                items.append(
                    f'<a href="{era}|{name}" style="text-decoration: none;">'
                    f'<span style="color: {own_color}; font-weight: 500;">'
                    f'{era} {name}{own_suffix}{vmark}</span>'
                    f'<span style="color: {rarity_color};"> ({rarity[0]})</span>'
                    f'</a>'
                )
            lbl = QLabel("<br>".join(items))
            lbl.setTextFormat(Qt.RichText)
            lbl.setOpenExternalLinks(False)
            lbl.linkActivated.connect(self._on_relic_link)
            lbl.setWordWrap(True)
            layout.addWidget(lbl)
        layout.addStretch(1)
        dlg.exec()

    # ============ Set Progress tab ============
    def _build_sets_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        sd = []
        for eq_name, eq in self.items_data.get("eqmt", {}).items():
            total = owned = crafted_n = need = 0
            for pname in eq.get("parts", {}).keys():
                total += 1
                target = pname if pname in self.owned else (pname + " Blueprint" if (pname + " Blueprint") in self.owned else pname)
                cnt = self.owned.get(target, 0) if isinstance(self.owned.get(target), int) else 0
                if cnt > 0:
                    owned += 1
                elif target in self.crafted or target in self.auto_crafted:
                    crafted_n += 1
                else:
                    need += 1
            if total == 0:
                continue
            done = owned + crafted_n
            sd.append({"name": eq_name, "type": eq.get("type", "?"), "vaulted": eq.get("vaulted", False),
                       "total": total, "owned": owned, "crafted": crafted_n, "need": need, "done": done,
                       "pct": done / total * 100 if total else 0})

        fr = QHBoxLayout()
        fr.addWidget(QLabel("Search:"))
        self.set_search = QLineEdit()
        self.set_search.setPlaceholderText("Filter by name")
        fr.addWidget(self.set_search, stretch=1)
        fr.addWidget(QLabel("Show:"))
        self.set_filter = QComboBox()
        self.set_filter.addItems(["All", "Incomplete only", "Almost done (>=75%)", "Just started (<=25%)", "Complete only"])
        fr.addWidget(self.set_filter)
        layout.addLayout(fr)

        self.set_summary = QLabel()
        layout.addWidget(self.set_summary)
        self.set_table = QTableWidget()
        self.set_table.setColumnCount(6)
        self.set_table.setHorizontalHeaderLabels(["Equipment", "Type", "V", "Progress", "Status", "Parts NEED"])
        self.set_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.set_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.set_table.setAlternatingRowColors(True)
        self.set_table.verticalHeader().setVisible(False)
        h = self.set_table.horizontalHeader()
        for c in range(6):
            h.setSectionResizeMode(c, QHeaderView.Interactive)
        layout.addWidget(self.set_table)
        apply_saved_widths(self.set_table, "set_table", [200, 90, 40, 140, 100, 220])
        remember_widths(self.set_table, "set_table")
        self._set_data = sd
        self.set_search.textChanged.connect(self._refresh_sets)
        self.set_filter.currentTextChanged.connect(self._refresh_sets)
        self._refresh_sets()
        return w

    def _refresh_sets(self):
        q = self.set_search.text().lower()
        flt = self.set_filter.currentText()
        filtered = []
        for s in self._set_data:
            if q and q not in s["name"].lower():
                continue
            if flt == "Incomplete only" and s["need"] == 0:
                continue
            if flt == "Almost done (>=75%)" and (s["pct"] < 75 or s["need"] == 0):
                continue
            if flt == "Just started (<=25%)" and s["pct"] > 25:
                continue
            if flt == "Complete only" and s["need"] > 0:
                continue
            filtered.append(s)
        filtered.sort(key=lambda s: (-s["pct"], s["name"]))

        self.set_table.setRowCount(len(filtered))
        for i, s in enumerate(filtered):
            _st0 = QTableWidgetItem(s["name"])
            _st0.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.set_table.setItem(i, 0, _st0)
            _st1 = QTableWidgetItem(s["type"]); _st1.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            self.set_table.setItem(i, 1, _st1)
            v = QTableWidgetItem("V" if s["vaulted"] else "")
            v.setForeground(QBrush(QColor("#888")))
            v.setTextAlignment(Qt.AlignCenter)
            self.set_table.setItem(i, 2, v)
            bar = QProgressBar()
            bar.setMaximum(s["total"])
            bar.setValue(s["done"])
            bar.setFormat(f"{s['done']}/{s['total']}")
            self.set_table.setCellWidget(i, 3, bar)
            sp = []
            if s["owned"]:
                sp.append(f"{s['owned']} in inventory")
            if s["crafted"]:
                sp.append(f"{s['crafted']} crafted")
            if s["need"]:
                sp.append(f"{s['need']} NEED")
            _st4 = QTableWidgetItem(", ".join(sp) or "-")
            _st4.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.set_table.setItem(i, 4, _st4)
            need_names = []
            eq = self.items_data.get("eqmt", {}).get(s["name"], {})
            for pname in eq.get("parts", {}).keys():
                target = pname if pname in self.owned else (pname + " Blueprint" if (pname + " Blueprint") in self.owned else pname)
                cnt = self.owned.get(target, 0) if isinstance(self.owned.get(target), int) else 0
                if cnt == 0 and target not in self.crafted and target not in self.auto_crafted:
                    short = pname.replace(s["name"] + " ", "")
                    need_names.append(short)
            _st5 = QTableWidgetItem(", ".join(need_names) if need_names else "-")
            _st5.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.set_table.setItem(i, 5, _st5)
        complete = sum(1 for s in self._set_data if s["need"] == 0)
        self.set_summary.setText(
            f"Showing {len(filtered)} of {len(self._set_data)} equipment "
            f"({complete} complete, {len(self._set_data) - complete} need >=1 part)"
        )

    # ============ Best Relics tab ============
    def _build_relics_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        info = QLabel(
            "<b>Best relics to crack for YOUR NEEDs.</b> "
            "Ranked by expected platinum value of NEED parts in each relic, "
            "weighted by Intact-solo drop chances. Double-click any row for full reward details."
        )
        info.setWordWrap(True)
        info.setStyleSheet("padding: 6px; color: #ccc;")
        layout.addWidget(info)
        fr = QHBoxLayout()
        fr.addWidget(QLabel("Era:"))
        self.r_era = QComboBox()
        self.r_era.addItems(["Any"] + ERAS)
        fr.addWidget(self.r_era)
        fr.addWidget(QLabel("Show:"))
        self.r_filter = QComboBox()
        self.r_filter.addItems(["Non-vaulted only", "All relics"])
        fr.addWidget(self.r_filter)
        self.r_owned_only = QCheckBox("Owned only")
        self.r_owned_only.setToolTip("Only show relics you currently own at least one of")
        fr.addWidget(self.r_owned_only)
        fr.addStretch(1)
        layout.addLayout(fr)
        self.r_summary = QLabel()
        layout.addWidget(self.r_summary)
        self.r_table = QTableWidget()
        self.r_table.setColumnCount(6)
        self.r_table.setHorizontalHeaderLabels(["Era", "Relic", "V", "EV (NEED)", "EV (total)", "NEED Drops"])
        self.r_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.r_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.r_table.setAlternatingRowColors(True)
        self.r_table.verticalHeader().setVisible(False)
        h = self.r_table.horizontalHeader()
        for c in range(6):
            h.setSectionResizeMode(c, QHeaderView.Interactive)
        self.r_table.cellDoubleClicked.connect(self._on_relic_row_click)
        layout.addWidget(self.r_table)
        apply_saved_widths(self.r_table, "r_table", [90, 160, 40, 90, 90, 260])
        remember_widths(self.r_table, "r_table")
        self._all_relic_stats = self._compute_relic_stats()
        self.r_era.currentTextChanged.connect(self._refresh_relics)
        self.r_filter.currentTextChanged.connect(self._refresh_relics)
        self.r_owned_only.stateChanged.connect(self._refresh_relics)
        self._refresh_relics()
        return w

    def _compute_relic_stats(self):
        stats = []
        for era in ERAS:
            era_data = self.items_data.get("relics", {}).get(era, {})
            for rname, relic in era_data.items():
                ev_t = ev_n = 0.0
                need_drops = []
                for field, rarity in RARITY_FIELDS.items():
                    p = relic.get(field)
                    if not p:
                        continue
                    cnt = _owned_count(self.owned, p)
                    is_owned = cnt > 0
                    is_crafted = (p in self.crafted or p in self.auto_crafted
                                  or (p + " Blueprint") in self.crafted
                                  or (p + " Blueprint") in self.auto_crafted)
                    plat = self.prices.get(p, self.prices.get(p + " Blueprint", 0))
                    ev = INTACT_CHANCES[rarity] * plat
                    ev_t += ev
                    if not is_owned and not is_crafted:
                        ev_n += ev
                        need_drops.append((p, rarity, plat))
                stats.append({"era": era, "name": rname, "vaulted": relic.get("vaulted", False),
                              "ev_total": ev_t, "ev_need": ev_n, "need_drops": need_drops})
        return stats

    def _refresh_relics(self):
        era_f = self.r_era.currentText()
        non_vaulted = self.r_filter.currentIndex() == 0
        owned_only = self.r_owned_only.isChecked()
        filtered = []
        for s in self._all_relic_stats:
            if era_f != "Any" and s["era"] != era_f:
                continue
            if non_vaulted and s["vaulted"]:
                continue
            if owned_only and self.owned_relics.get(f"{s['era']} {s['name']}", {}).get("owned", 0) == 0:
                continue
            filtered.append(s)
        filtered.sort(key=lambda s: -s["ev_need"])
        self.r_table.setRowCount(len(filtered))
        for i, s in enumerate(filtered):
            _rt0 = QTableWidgetItem(s["era"])
            _rt0.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            self.r_table.setItem(i, 0, _rt0)
            _rt1 = QTableWidgetItem(s["name"])
            _rt1.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.r_table.setItem(i, 1, _rt1)
            v = QTableWidgetItem("V" if s["vaulted"] else "")
            v.setForeground(QBrush(QColor("#888")))
            v.setTextAlignment(Qt.AlignCenter)
            self.r_table.setItem(i, 2, v)
            en = QTableWidgetItem(f"{s['ev_need']:.2f}p")
            en.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if s["ev_need"] > 5:
                en.setForeground(QBrush(QColor("#67d164")))
            self.r_table.setItem(i, 3, en)
            et = QTableWidgetItem(f"{s['ev_total']:.2f}p")
            et.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.r_table.setItem(i, 4, et)
            drops_text = ", ".join(f"{p} ({r[0]}, {pp:.0f}p)" for p, r, pp in s["need_drops"]) or "(none)"
            _rt5 = QTableWidgetItem(drops_text)
            _rt5.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.r_table.setItem(i, 5, _rt5)
        non_zero = sum(1 for s in filtered if s["ev_need"] > 0)
        self.r_summary.setText(
            f"Showing {len(filtered)} relics ({non_zero} have NEED drops). "
            f"Double-click any row for full details."
        )

    def _on_relic_row_click(self, row, col):
        if row < 0:
            return
        era_item = self.r_table.item(row, 0)
        name_item = self.r_table.item(row, 1)
        if not era_item or not name_item:
            return
        self._show_relic(era_item.text(), name_item.text())


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(WFINFO_ICON))
    app.setStyleSheet(get_theme(load_theme()))

    # Show first-run disclaimer if not yet accepted
    try:
        from disclaimer import check_and_show_disclaimer
        if not check_and_show_disclaimer():
            sys.exit(0)   # user clicked Exit
    except Exception as e:
        print(f"[disclaimer] error: {e}", file=sys.stderr)

    t = Tracker()
    t.show()
    ret = app.exec()
    # Save window geometry on exit
    if hasattr(t, '_settings'):
        t._settings.setValue("geometry", t.saveGeometry())
    sys.exit(ret)


if __name__ == "__main__":
    main()