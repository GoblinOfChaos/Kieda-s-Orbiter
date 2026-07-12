#!/usr/bin/env python3
"""Dashboard Tab — Live Warframe world state.

Polls api.warframestat.us every 60 seconds and shows:
- Void Fissures (grouped by tier, with Rad fissures highlighted)
- Sortie & Archon Hunt
- Arbitration
- Baro Ki'Teer / Void Trader
- Day/Night cycles (Cetus, Vallis, Cambion, Duviri)
- Nightwave challenges
- Steel Path incursions
"""

import json
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QGridLayout, QPushButton, QSizePolicy, QSizePolicy as QSP,
)
from paths import DATA_DIR
from theme import (
    get_palette,
    BG_DEEP as BG, BG_PANEL, BG_CARD, BG_HEADER,
    GOLD, GOLD_BRIGHT, SAP_BRIGHT as SAP, SAP_MID, SAP_DIM,
    FG, FG_DIM as DIM,
    BORDER, BORDER_BRIGHT,
    COLOR_GREAT as GREEN, COLOR_BAD as RED, COLOR_WARN as ORANGE,
)

API_URL = "https://api.warframestat.us/pc?language=en"
REFRESH_INTERVAL_MS = 60_000   # 1 minute
CACHE_FILE = DATA_DIR / "worldstate_cache.json"

# api.warframestat.us doesn't expose Descendia (the Tau/Zariman roguelite
# mode) yet, so it needs its own fetch from the raw worldstate mirror that
# Cephalon Kronos also relies on for this same data.
DESCENDIA_API_URL = "https://oracle.browse.wf/worldState.json"
DESCENDIA_CACHE_FILE = DATA_DIR / "descendia_cache.json"

# Fallback display names for Descendia stage types/modifiers when the raw
# worldstate only gives internal codenames. Verified against Cephalon
# Kronos's DESCENDIA_MISSION_TYPES/DESCENDIA_PENANCES tables.
DESCENDIA_MISSION_TYPES = {
    "DT_BREAK_TARGETS": "Destroy Hologlobes",
    "DT_LOOT_CREATURES": "Gruzzling Plunder",
    "DT_ALCHEMY": "Alchemy",
    "DT_INTERCEPTION": "Mobile Interception",
    "DT_INFESTED_SALVAGE": "Infested Salvage",
    "DT_SABOTAGE_HIVE": "Hive",
    "DT_PROTOFRAME": "Protoframe Room",
    "DT_CAPTURE": "Capture",
    "DT_MIMICS": "Plunder Roulette",
    "DT_COLLECTION": "Void Flood",
    "DT_BOSS": "Assassination",
    "DT_EXTERMINATE": "Exterminate",
    "DT_NETRACELLS": "Targeted Elimination",
    "DT_SABOTAGE_DEFENSE": "Defense",
    "DT_DEFENSE": "Defense of a Protoframe",
    "DT_EXCAVATION": "Excavation",
    "DT_PRESURE_GAUGE": "Volatile",
    "DT_UNIQUE": "Unique",
    "DT_LOOT": "Loot",
    "DT_RACE": "Race",
}

DESCENDIA_PENANCES = {
    "NC_SlipAndSlide": "Frictionless without Enemies",
    "BasicLootCreatures": "Gruzzling Plunder",
    "MineField": "Minefield",
    "SlipAndSlide": "Frictionless",
    "Escapist": "Sneaky Retreats",
    "VoidAberration": "Vampyric Liminus",
    "Wisp": "Marie",
    "FireAndIce": "Eximus Cabal: Fire & Ice",
    "BasicMimics": "Plunder Roulette",
    "NC_MineField": "Minefield without Enemies",
    "Octopede": "The Fragmented Boss",
    "PoisonGas": "Chemical Warfare",
    "GlassMaker": "Glassmaker Cephalites",
    "Harrow": "Lyon",
    "Darkness": "Sol Banished",
    "SpicyKnife": "Bomb Defusal",
    "JumpSmash": "Head Stompers",
    "Manics": "Manic Mania",
    "FireChain": "Fire Chain",
}

# Tier colors
TIER_COLORS = {
    "Lith":    "#8fd3ff",
    "Meso":    "#7fffb0",
    "Neo":     "#ffb37f",
    "Axi":     "#ff8fa3",
    "Requiem": "#d0a3ff",
    "Omnia":   "#ffd24c",
    "Vanguard":"#c9a84c",
}

# Cycle state colors/icons — all BMP safe
CYCLE_ICONS = {
    "day":    ("☀",  "#ffd24c"),   # sun
    "night":  ("☽", "#8fd3ff"),   # crescent moon
    "warm":   ("▲", "#ff9933"),   # warm/up triangle
    "cold":   ("❄",  "#8fd3ff"),   # snowflake
    "fass":   ("●", "#ff9933"),   # Fass (orange wyrm)
    "vome":   ("○", "#8fd3ff"),   # Vome (blue wyrm)
    "anger":  ("▲", "#ff6060"),   # anger
    "joy":    ("★", "#ffd24c"),   # joy/star
    "envy":   ("◆", "#7fffb0"),   # envy/diamond
    "sorrow": ("▽", "#8fd3ff"),   # sorrow/down
    "fear":   ("◇", "#d0a3ff"),   # fear/open diamond
}

# Faction color badges — color-coded dots matching Warframe's faction colors
FACTION_COLORS = {
    "Grineer":    "#e85c0d",   # orange-red
    "Corpus":     "#3cb4e6",   # cyan-blue
    "Infestation":"#6dbf4a",   # green
    "Infested":   "#6dbf4a",
    "Corrupted":  "#c9a84c",   # gold
    "Murmur":     "#c084fc",   # purple
    "Narmer":     "#f0c040",   # golden yellow
    "Sentient":   "#e040fb",   # violet
    "Tenno":      "#3cb4e6",
    "Crossfire":  "#aaaaaa",
}

# Mission type icons — all BMP safe
MISSION_ICONS = {
    "Extermination": "⚔",   # crossed swords
    "Survival":      "⧖",   # hourglass
    "Defense":       "■",   # square shield
    "Mobile Defense":"▣",   # filled square
    "Interception":  "◎",   # bullseye
    "Capture":       "◆",   # diamond
    "Rescue":        "▷",   # triangle
    "Sabotage":      "✶",   # 6-point star
    "Spy":           "◇",   # open diamond
    "Assassination": "☠",   # skull
    "Excavation":    "⛏",   # pick
    "Defection":     "▸",   # small triangle
    "Junction":      "□",   # open square
    "Skirmish":      "△",   # open triangle
    "Pursuit":       "▶",   # filled triangle
    "Alchemy":       "⚗",   # retort
    "Void Cascade":  "○",   # open circle
    "Disruption":    "⚡",   # lightning
    "Onslaught":     "▲",   # up triangle
    "Elite Onslaught":"▲",  # up triangle
    "Void Armageddon":"✶",  # star
    "Void Flood":    "≈",   # approx
}




def _p():
    """Return current theme palette — always fresh, never stale."""
    return get_palette()


def _card_style():
    p = _p()
    return (
        f"background: {p['bg_panel']}; border: 1px solid {p['border']}; "
        f"border-radius: 8px;"
    )


def _section_title(text, accent_color=None):
    p = _p()
    w = QWidget()
    w.setStyleSheet(
        f"background: {p['bg_card']}; border-radius: 6px 6px 0 0; "
        f"border-bottom: 1px solid {p['border']};"
    )
    row = QHBoxLayout(w)
    row.setContentsMargins(10, 7, 10, 7)
    row.setSpacing(8)
    if accent_color:
        bar = QWidget()
        bar.setFixedWidth(3)
        bar.setFixedHeight(14)
        bar.setStyleSheet(f"background: {accent_color}; border-radius: 2px;")
        row.addWidget(bar)
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {p['gold']}; font-size: 12px; font-weight: 700; "
        f"letter-spacing: 0.5px; background: transparent;"
    )
    row.addWidget(lbl)
    row.addStretch()
    return w


def _label(text, color=None, size=13, bold=False, wrap=False):
    p = _p()
    lbl = QLabel(text)
    weight = "700" if bold else "400"
    lbl.setStyleSheet(
        f"color: {color or p['fg']}; font-size: {size}px; "
        f"font-weight: {weight}; background: transparent;"
    )
    lbl.setWordWrap(wrap)
    return lbl


def _row_divider():
    p = _p()
    d = QFrame()
    d.setFrameShape(QFrame.HLine)
    d.setStyleSheet(f"color: {p['border']}; background: {p['border']};")
    d.setFixedHeight(1)
    return d


def _faction_badge(faction: str) -> QWidget:
    color = FACTION_COLORS.get(faction, _p()['fg_dim'])
    w = QLabel(faction)
    w.setStyleSheet(
        f"color: {color}; font-size: 11px; font-weight: 700; "
        f"background: transparent; padding: 0;"
    )
    return w


def _mission_row(mission_type: str, node: str, modifier: str = "", faction: str = "") -> QWidget:
    """A single mission row with icon, type, node, and optional modifier."""
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    vl = QVBoxLayout(w)
    vl.setContentsMargins(0, 3, 0, 3)
    vl.setSpacing(2)

    top = QHBoxLayout()
    top.setSpacing(8)
    icon = MISSION_ICONS.get(mission_type, "•")
    icon_lbl = QLabel(icon)
    icon_lbl.setStyleSheet(f"color: {GOLD}; font-size: 14px; background: transparent;")
    icon_lbl.setFixedWidth(22)
    icon_lbl.setAlignment(Qt.AlignCenter)
    top.addWidget(icon_lbl)

    # Mission type bold, then node dimmed — all on one line, no wrapping
    combo_lbl = QLabel(f"<b style='color:{FG};'>{mission_type}</b>"
                       f"<span style='color:{DIM};'>  ·  {node}</span>")
    combo_lbl.setTextFormat(Qt.RichText)
    combo_lbl.setStyleSheet("background: transparent; font-size: 13px;")
    top.addWidget(combo_lbl, stretch=1)
    vl.addLayout(top)

    if modifier:
        mod_lbl = QLabel(f"<i style='color:{ORANGE};'>{modifier}</i>")
        mod_lbl.setTextFormat(Qt.RichText)
        mod_lbl.setStyleSheet(
            f"background: #162848; border-radius: 3px; "
            f"padding: 1px 8px 1px 30px; font-size: 11px;"
        )
        mod_lbl.setWordWrap(True)
        vl.addWidget(mod_lbl)

    return w


class _Fetcher(QObject):
    data_ready = Signal(dict)
    error = Signal(str)

    def __init__(self, url=API_URL, cache_file=CACHE_FILE, parent=None):
        super().__init__(parent)
        self._url = url
        self._cache_file = cache_file

    def fetch(self):
        def _run():
            try:
                req = urllib.request.Request(
                    self._url, headers={"User-Agent": "kiedas-orbiter/1.0"}
                )
                with urllib.request.urlopen(req, timeout=15) as r:
                    raw = r.read()
                data = json.loads(raw)
                self._cache_file.parent.mkdir(parents=True, exist_ok=True)
                self._cache_file.write_bytes(raw)
                self.data_ready.emit(data)
            except Exception as e:
                # Try cache
                try:
                    data = json.loads(self._cache_file.read_text())
                    self.data_ready.emit(data)
                except Exception:
                    self.error.emit(str(e))
        threading.Thread(target=_run, daemon=True).start()


def _mongo_date_to_iso(field) -> str | None:
    """Convert a MongoDB extended-JSON date field ({"$date": {"$numberLong":
    "..."}} or {"$date": "..."}) to an ISO string _expiry_str understands."""
    if not isinstance(field, dict):
        return None
    d = field.get("$date")
    if isinstance(d, dict) and "$numberLong" in d:
        try:
            ms = int(d["$numberLong"])
            return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()
        except Exception:
            return None
    if isinstance(d, str):
        return d
    return None


def _expiry_str(expiry_iso: str | None) -> str:
    """Convert ISO expiry to a human-readable time remaining string."""
    if not expiry_iso:
        return ""
    try:
        expiry = datetime.fromisoformat(expiry_iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = expiry - now
        if delta.total_seconds() < 0:
            return "expired"
        total = int(delta.total_seconds())
        days = total // 86400
        h, rem = divmod(total % 86400, 3600)
        m = rem // 60
        if days > 0:
            return f"{days}d {h}h"
        if h > 0:
            return f"{h}h {m}m"
        return f"{m}m"
    except Exception:
        return ""


class DashboardTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = None
        self._descendia_data = None
        self._fetcher = _Fetcher()
        self._fetcher.data_ready.connect(self._on_data)
        self._fetcher.error.connect(self._on_error)
        self._descendia_fetcher = _Fetcher(url=DESCENDIA_API_URL, cache_file=DESCENDIA_CACHE_FILE)
        self._descendia_fetcher.data_ready.connect(self._on_descendia_data)
        self._descendia_fetcher.error.connect(lambda *_: None)  # optional section — fail silently
        self._setup_ui()

        # Auto-refresh timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(REFRESH_INTERVAL_MS)

        # Initial fetch
        self._refresh()

    def _setup_ui(self):
        p = _p()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Top bar: title + last-updated + refresh button
        self._topbar = QFrame()
        tb = QHBoxLayout(self._topbar)
        tb.setContentsMargins(12, 6, 12, 6)
        self._title_lbl = QLabel("●  Live World State")
        tb.addWidget(self._title_lbl)
        tb.addStretch()
        self._last_updated_lbl = QLabel("Fetching...")
        tb.addWidget(self._last_updated_lbl)
        self._refresh_btn = QPushButton("↻")
        self._refresh_btn.setMaximumWidth(32)
        self._refresh_btn.setToolTip("Refresh now")
        self._refresh_btn.clicked.connect(self._refresh)
        tb.addWidget(self._refresh_btn)
        outer.addWidget(self._topbar)

        # Scrollable content
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(10, 10, 10, 10)
        self._content_layout.setSpacing(10)
        self._scroll.setWidget(self._content)
        outer.addWidget(self._scroll, stretch=1)

        self._loading_lbl = QLabel("Loading world state...")
        self._loading_lbl.setAlignment(Qt.AlignCenter)
        self._content_layout.addWidget(self._loading_lbl)

        # Apply initial styles (no rebuild — no data yet)
        p = _p()
        self._topbar.setStyleSheet(
            f"background: {p['bg_panel']}; border-bottom: 1px solid {p['border']};"
        )
        self._title_lbl.setStyleSheet(
            f"color: {p['gold']}; font-size: 14px; font-weight: 700; background: transparent;"
        )
        self._last_updated_lbl.setStyleSheet(
            f"color: {p['fg_dim']}; font-size: 11px; background: transparent;"
        )
        self._refresh_btn.setStyleSheet(
            f"QPushButton {{ background: {p['bg_card']}; color: {p['accent']}; "
            f"border: 1px solid {p['border']}; border-radius: 4px; font-size: 14px; padding: 2px 6px; }}"
            f"QPushButton:hover {{ color: {p['gold']}; border-color: {p['accent']}; }}"
        )
        self._scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {p['bg']}; }}")
        self._content.setStyleSheet(f"background: {p['bg']};")
        self._loading_lbl.setStyleSheet(f"color: {p['fg_dim']}; font-size: 13px; padding: 40px;")

    def _apply_styles(self):
        """Re-apply structural styles and rebuild cards with current theme palette."""
        p = _p()
        self._topbar.setStyleSheet(
            f"background: {p['bg_panel']}; border-bottom: 1px solid {p['border']};"
        )
        self._title_lbl.setStyleSheet(
            f"color: {p['gold']}; font-size: 14px; font-weight: 700; background: transparent;"
        )
        self._last_updated_lbl.setStyleSheet(
            f"color: {p['fg_dim']}; font-size: 11px; background: transparent;"
        )
        self._refresh_btn.setStyleSheet(
            f"QPushButton {{ background: {p['bg_card']}; color: {p['accent']}; "
            f"border: 1px solid {p['border']}; border-radius: 4px; font-size: 14px; padding: 2px 6px; }}"
            f"QPushButton:hover {{ color: {p['gold']}; border-color: {p['accent']}; }}"
        )
        self._scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {p['bg']}; }}"
        )
        self._content.setStyleSheet(f"background: {p['bg']};")
        # Rebuild cards with new theme colors (only if data already loaded)
        if self._data is not None:
            self._rebuild()

    def _refresh(self):
        self._last_updated_lbl.setText("Refreshing...")
        self._fetcher.fetch()
        self._descendia_fetcher.fetch()

    def _on_error(self, msg):
        self._last_updated_lbl.setText(f"Error: {msg[:50]}")

    def _on_data(self, data):
        self._data = data
        now = datetime.now().strftime("%H:%M:%S")
        self._last_updated_lbl.setText(f"Updated {now}")
        self._rebuild()

    def _on_descendia_data(self, data):
        self._descendia_data = data
        if self._data is not None:
            self._rebuild()

    def _clear(self):
        self._loading_lbl = None  # will be gone after deleteLater
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _rebuild(self):
        self._clear()
        d = self._data
        if not d:
            return

        # ── Layout: two columns ──────────────────────────────────────────
        grid = QWidget()
        grid_layout = QGridLayout(grid)
        grid_layout.setSpacing(10)
        grid_layout.setContentsMargins(0, 0, 0, 0)

        col0 = QVBoxLayout()
        col0.setSpacing(10)
        col1 = QVBoxLayout()
        col1.setSpacing(10)

        col0.addWidget(self._build_cycles(d))
        col0.addWidget(self._build_fissures(d))
        col0.addWidget(self._build_nightwave(d))
        col0.addStretch()

        col1.addWidget(self._build_sortie(d))
        col1.addWidget(self._build_archon(d))
        col1.addWidget(self._build_arbitration(d))
        col1.addWidget(self._build_baro(d))
        col1.addWidget(self._build_steel_path(d))
        descendia_card = self._build_descendia()
        if descendia_card is not None:
            col1.addWidget(descendia_card)
        col1.addStretch()

        col0_w = QWidget(); col0_w.setLayout(col0)
        col1_w = QWidget(); col1_w.setLayout(col1)

        grid_layout.addWidget(col0_w, 0, 0)
        grid_layout.addWidget(col1_w, 0, 1)
        grid_layout.setColumnStretch(0, 3)
        grid_layout.setColumnStretch(1, 2)

        self._content_layout.addWidget(grid)

    # ── Section builders ─────────────────────────────────────────────────

    def _build_cycles(self, d):
        frame = QFrame()
        frame.setStyleSheet(_card_style())
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_section_title("☀  CYCLES", SAP))

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(12, 8, 12, 10)
        body_layout.setSpacing(5)

        CYCLES = [
            ("earthCycle",   "Earth"),
            ("cetusCycle",   "Cetus"),
            ("vallisCycle",  "Orb Vallis"),
            ("cambionCycle", "Cambion Drift"),
            ("duviriCycle",  "Duviri"),
        ]

        grid = QGridLayout()
        grid.setSpacing(4)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setColumnMinimumWidth(0, 100)   # location name
        grid.setColumnMinimumWidth(1, 95)    # state icon+text
        grid.setColumnStretch(2, 1)           # flex spacer pushes timer right
        grid.setColumnMinimumWidth(3, 90)    # timer - wide enough for '1h 40m 0s'

        for row_idx, (key, name) in enumerate(CYCLES):
            c = d.get(key, {})
            state = c.get("state", "unknown")
            raw_tl = c.get("timeLeft")
            if raw_tl:
                time_left = raw_tl
            else:
                exp = _expiry_str(c.get("expiry"))
                time_left = exp if exp and exp != "expired" else "—"
            icon, color = CYCLE_ICONS.get(state, ("\u25cb", DIM))

            name_lbl = _label(name, DIM, 12)
            name_lbl.setWordWrap(False)
            name_lbl.setFixedWidth(100)

            state_lbl = _label(f"{icon} {state.capitalize()}", color, 12, bold=True)
            state_lbl.setWordWrap(False)
            state_lbl.setFixedWidth(95)
            state_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            time_lbl = _label(time_left or "\u2014", DIM, 12)
            time_lbl.setWordWrap(False)
            time_lbl.setFixedWidth(90)  # wide enough for '1h 32m 0s'
            time_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            grid.addWidget(name_lbl,  row_idx, 0)
            grid.addWidget(state_lbl, row_idx, 1)
            # col 2 is the stretch spacer - no widget needed, just stretch
            grid.addWidget(time_lbl,  row_idx, 3)

        body_layout.addLayout(grid)

        layout.addWidget(body)
        return frame

    def _build_fissures(self, d):
        frame = QFrame()
        frame.setStyleSheet(_card_style())
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_section_title("◆  VOID FISSURES", GOLD))

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(12, 8, 12, 10)
        body_layout.setSpacing(2)

        fissures = d.get("fissures", [])
        tier_order = ["Lith", "Meso", "Neo", "Axi", "Requiem", "Omnia", "Vanguard"]
        by_tier = {}
        for f in fissures:
            tier = f.get("tier", "?")
            by_tier.setdefault(tier, []).append(f)

        for tier in tier_order:
            fs = by_tier.get(tier, [])
            if not fs:
                continue
            color = TIER_COLORS.get(tier, FG)

            # Tier header row
            tier_row = QHBoxLayout()
            tier_row.setContentsMargins(0, 6, 0, 2)
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 10px; background: transparent;")
            tier_name = QLabel(tier)
            tier_name.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 700; background: transparent;")
            tier_row.addWidget(dot)
            tier_row.addWidget(tier_name)
            tier_row.addStretch()
            body_layout.addLayout(tier_row)

            for f in fs:
                mission = f.get("missionType", "")
                node = f.get("node", "")
                eta = _expiry_str(f.get("expiry"))
                is_hard = f.get("isHard", False)
                is_storm = f.get("isStorm", False)

                suffix = ""
                if is_hard:
                    suffix += " ●"
                if is_storm:
                    suffix += " ⚡"

                row = QHBoxLayout()
                row.setContentsMargins(14, 0, 0, 0)
                row.setSpacing(8)
                info = _label(f"{mission} — {node}{suffix}", FG, 12)
                info.setWordWrap(False)
                eta_lbl = _label(eta or "—", DIM, 11)
                eta_lbl.setWordWrap(False)
                eta_lbl.setFixedWidth(52)
                eta_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                row.addWidget(info, stretch=1)
                row.addWidget(eta_lbl)
                body_layout.addLayout(row)

        if not fissures:
            body_layout.addWidget(_label("No active fissures", DIM, 13))

        layout.addWidget(body)
        return frame

    def _build_sortie(self, d):
        frame = QFrame()
        frame.setStyleSheet(_card_style())
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_section_title("⚔  SORTIE", ORANGE))

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(12, 10, 12, 12)
        body_layout.setSpacing(8)

        s = d.get("sortie", {})
        boss = s.get("boss", "")
        faction = s.get("faction", "")
        faction_color = FACTION_COLORS.get(faction, DIM)
        eta = _expiry_str(s.get("expiry"))

        # Header: boss name + faction badge + timer
        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        boss_lbl = _label(boss, FG, 15, bold=True)
        header_row.addWidget(boss_lbl)
        header_row.addWidget(_faction_badge(faction))
        header_row.addStretch()
        header_row.addWidget(_label(eta, DIM, 12))
        body_layout.addLayout(header_row)
        body_layout.addWidget(_row_divider())

        for v in s.get("variants", []):
            body_layout.addWidget(_mission_row(
                v.get("missionType", ""),
                v.get("node", ""),
                v.get("modifier", ""),
                faction,
            ))

        layout.addWidget(body)
        return frame

    def _build_archon(self, d):
        frame = QFrame()
        frame.setStyleSheet(_card_style())
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_section_title("■  ARCHON HUNT", SAP))

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(12, 10, 12, 12)
        body_layout.setSpacing(8)

        ah = d.get("archonHunt", {})
        boss = ah.get("boss", "")
        faction = ah.get("faction", "")
        eta = _expiry_str(ah.get("expiry"))

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        header_row.addWidget(_label(boss, FG, 15, bold=True))
        header_row.addWidget(_faction_badge(faction))
        header_row.addStretch()
        header_row.addWidget(_label(eta, DIM, 12))
        body_layout.addLayout(header_row)
        body_layout.addWidget(_row_divider())

        for m in ah.get("missions", []):
            body_layout.addWidget(_mission_row(
                m.get("type", ""),
                m.get("node", ""),
            ))

        layout.addWidget(body)
        return frame

    def _build_arbitration(self, d):
        frame = QFrame()
        frame.setStyleSheet(_card_style())
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_section_title("◎  ARBITRATION", GREEN))

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(12, 8, 12, 10)
        body_layout.setSpacing(5)

        a = d.get("arbitration", {})
        node = a.get("node", "")
        mission = a.get("type", "")
        enemy = a.get("enemy", "")
        eta = _expiry_str(a.get("expiry"))
        archwing = a.get("archwing", False)
        sharkwing = a.get("sharkwing", False)

        # Detect placeholder (API returns SolNode000/Unknown when none active)
        is_placeholder = (not node or node == "SolNode000" or mission == "Unknown")

        if is_placeholder:
            body_layout.addWidget(_label("No active Arbitration right now", DIM, 13))
        else:
            suffix = " (Archwing)" if archwing else " (Sharkwing)" if sharkwing else ""
            icon = MISSION_ICONS.get(mission, "•")

            header_row = QHBoxLayout()
            header_row.setSpacing(8)
            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet(f"color: {GOLD}; font-size: 15px; background: transparent;")
            icon_lbl.setFixedWidth(22)
            icon_lbl.setAlignment(Qt.AlignCenter)
            header_row.addWidget(icon_lbl)
            header_row.addWidget(_label(f"{node}{suffix}", FG, 14, bold=True))
            header_row.addStretch()
            header_row.addWidget(_label(eta, DIM, 12))
            body_layout.addLayout(header_row)

            detail_row = QHBoxLayout()
            detail_row.setSpacing(8)
            detail_row.addWidget(_label(mission, DIM, 12))
            if enemy:
                detail_row.addWidget(_faction_badge(enemy))
            detail_row.addStretch()
            body_layout.addLayout(detail_row)

        layout.addWidget(body)
        return frame

    def _build_baro(self, d):
        frame = QFrame()
        vt = d.get("voidTrader", {})
        inventory = vt.get("inventory", [])
        active = bool(inventory)
        frame.setStyleSheet(_card_style())
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_section_title("◆  BARO KI'TEER", GOLD if active else DIM))

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(12, 8, 12, 10)
        body_layout.setSpacing(5)

        location = vt.get("location", "")
        eta = _expiry_str(vt.get("expiry")) if active else _expiry_str(vt.get("activation"))

        if active:
            header_row = QHBoxLayout()
            header_row.addWidget(_label(f"✓ Here now  ·  {location}", GREEN, 14, bold=True))
            header_row.addStretch()
            header_row.addWidget(_label(f"Leaves {eta}", DIM, 12))
            body_layout.addLayout(header_row)
            body_layout.addWidget(_label(f"{len(inventory)} items for sale", DIM, 12))
            body_layout.addWidget(_row_divider())
            for item in inventory[:5]:
                name = item.get("item", item.get("ItemType", "?"))
                ducats = item.get("DucatPrice", item.get("ducatPrice", 0))
                credits = item.get("CreditPrice", item.get("creditPrice", 0))
                item_row = QHBoxLayout()
                item_row.addWidget(_label(name, FG, 13))
                item_row.addStretch()
                item_row.addWidget(_label(f"{ducats}◆ + {credits:,}cr", DIM, 12))
                body_layout.addLayout(item_row)
            if len(inventory) > 5:
                body_layout.addWidget(_label(f"+ {len(inventory)-5} more items", DIM, 12))
        else:
            header_row = QHBoxLayout()
            header_row.addWidget(_label("Not here", DIM, 14, bold=True))
            header_row.addStretch()
            header_row.addWidget(_label(f"Arrives in {eta}", DIM, 12))
            body_layout.addLayout(header_row)
            body_layout.addWidget(_label(f"Location: {location}", DIM, 13))

        layout.addWidget(body)
        return frame

    def _build_steel_path(self, d):
        frame = QFrame()
        frame.setStyleSheet(_card_style())
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_section_title("✶  STEEL PATH", GOLD))

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(12, 8, 12, 10)
        body_layout.setSpacing(5)

        sp = d.get("steelPath", {})
        current = sp.get("currentReward", {})
        reward_name = current.get("name", "")
        reward_cost = current.get("cost", 0)
        eta = _expiry_str(sp.get("expiry"))

        if reward_name:
            row = QHBoxLayout()
            row.addWidget(_label(reward_name, FG, 14, bold=True))
            row.addStretch()
            row.addWidget(_label(f"{reward_cost} essence", DIM, 12))
            body_layout.addLayout(row)
            body_layout.addWidget(_label(f"Rotates in {eta}", DIM, 13))
        else:
            body_layout.addWidget(_label("No current reward data", DIM, 13))

        layout.addWidget(body)
        return frame

    def _build_nightwave(self, d):
        frame = QFrame()
        frame.setStyleSheet(_card_style())
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_section_title("○  NIGHTWAVE", "#7fffb0"))

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(12, 8, 12, 10)
        body_layout.setSpacing(4)

        nw = d.get("nightwave", {})
        challenges = nw.get("activeChallenges", [])

        daily  = [c for c in challenges if c.get("isDaily")]
        weekly = [c for c in challenges if not c.get("isDaily") and not c.get("isElite")]
        elite  = [c for c in challenges if c.get("isElite")]

        for group, group_label, accent in [
            (daily,  "Daily",       "#ffd24c"),
            (weekly, "Weekly",      "#7fffb0"),
            (elite,  "Elite Weekly","#ff8fa3"),
        ]:
            if not group:
                continue
            body_layout.addWidget(_label(group_label, accent, 12, bold=True))
            for ch in group:
                title = ch.get("title", "")
                rep   = ch.get("reputation", 0)
                done  = ch.get("completed", False)
                check = "✓  " if done else "○  "
                text_color = DIM if done else FG
                rep_color  = DIM if done else "#7fffb0"
                row = QHBoxLayout()
                row.setContentsMargins(8, 0, 0, 0)
                row.setSpacing(6)
                title_lbl = _label(f"{check}{title}", text_color, 12)
                title_lbl.setWordWrap(False)  # no wrap — elide instead
                title_lbl.setSizePolicy(
                    title_lbl.sizePolicy().horizontalPolicy(),
                    title_lbl.sizePolicy().verticalPolicy()
                )
                rep_lbl = _label(f"+{rep:,}", rep_color, 12)
                rep_lbl.setFixedWidth(52)
                rep_lbl.setAlignment(Qt.AlignRight)
                row.addWidget(title_lbl, stretch=1)
                row.addWidget(rep_lbl)
                body_layout.addLayout(row)

        if not challenges:
            body_layout.addWidget(_label("No active challenges", DIM, 13))

        layout.addWidget(body)
        return frame

    def _build_descendia(self):
        """Descendia (the Tau/Zariman roguelite 'Descent' mode) isn't in
        api.warframestat.us yet, so this reads from self._descendia_data
        (fetched separately from oracle.browse.wf/worldState.json) instead
        of the main dashboard payload. Returns None if that data hasn't
        loaded yet, so the caller can skip adding this card entirely."""
        wd = self._descendia_data
        if not wd:
            return None
        descents = wd.get("Descents", [])
        if not descents:
            return None

        now = datetime.now(timezone.utc)
        current = None
        for desc in descents:
            activation = _mongo_date_to_iso(desc.get("Activation"))
            expiry = _mongo_date_to_iso(desc.get("Expiry"))
            try:
                if activation and expiry:
                    a = datetime.fromisoformat(activation)
                    e = datetime.fromisoformat(expiry)
                    if a <= now <= e:
                        current = desc
                        break
            except Exception:
                continue
        if current is None:
            current = descents[-1]

        frame = QFrame()
        frame.setStyleSheet(_card_style())
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_section_title("◈  DESCENDIA", "#c084fc"))

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(12, 8, 12, 10)
        body_layout.setSpacing(2)

        eta = _expiry_str(_mongo_date_to_iso(current.get("Expiry")))
        header_row = QHBoxLayout()
        header_row.addWidget(_label("This week's Descent", FG, 13, bold=True))
        header_row.addStretch()
        header_row.addWidget(_label(f"Resets {eta}" if eta else "", DIM, 12))
        body_layout.addLayout(header_row)
        body_layout.addWidget(_row_divider())

        stages = sorted(current.get("Challenges", []), key=lambda c: c.get("Index", 0))
        for stage in stages:
            index = stage.get("Index", 0)
            raw_type = stage.get("Type", "")
            raw_penance = stage.get("Challenge", "")
            mission_type = DESCENDIA_MISSION_TYPES.get(raw_type, raw_type)
            penance = DESCENDIA_PENANCES.get(raw_penance, raw_penance)
            is_checkpoint = index in (7, 14, 21)
            is_boss = index == 21

            row = QHBoxLayout()
            row.setContentsMargins(0, 2, 0, 2)
            row.setSpacing(8)
            marker_color = "#ff8fa3" if is_boss else (GOLD if is_checkpoint else DIM)
            marker = _label(f"{index:>2}", marker_color, 11, bold=is_checkpoint)
            marker.setFixedWidth(20)
            row.addWidget(marker)
            label_color = FG if is_checkpoint else DIM
            text = f"{mission_type} — {penance}" if penance else mission_type
            info_lbl = _label(text, label_color, 12, bold=is_boss)
            info_lbl.setWordWrap(False)
            row.addWidget(info_lbl, stretch=1)
            if is_boss:
                row.addWidget(_label("BOSS", "#ff8fa3", 10, bold=True))
            elif is_checkpoint:
                row.addWidget(_label("checkpoint", GOLD, 10))
            body_layout.addLayout(row)

        layout.addWidget(body)
        return frame