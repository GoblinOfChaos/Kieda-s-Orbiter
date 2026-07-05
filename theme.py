"""Kieda's Orbiter theme — Porsche sapphire blue metallic with metallic gold accents."""

# ── Palette ────────────────────────────────────────────────────────────────
# Backgrounds inspired by Porsche Sapphire Blue Metallic:
#   Deep base: rich jewel-toned blue with a slight teal shift (#0e1e3a)
#   Panel:     mid-depth sapphire (#162a4e)
#   Card:      slightly lighter with metallic shimmer (#1d3560)
#   Input:     darkened sapphire for contrast (#0b1830)
#   Header:    deep but distinct from panel (#12244a)
#
# The key is the BORDER and selection colors pulling from the brighter
# metallic sapphire highlight (#2e6db4 / #4a90d9) — this gives the
# metallic "sheen" feeling without being flat or navy.

BG_DEEP      = "#0b1628"   # deep sapphire base — main window
BG_PANEL     = "#122040"   # rich sapphire panel
BG_CARD      = "#1a2e55"   # metallic sapphire card / alternating rows
BG_INPUT     = "#0e1a35"   # darkened sapphire — inputs
BG_HEADER    = "#0f1e3d"   # column headers — slightly deeper than panel

# Sapphire metallic highlight spectrum (the "metallic" part — cooler, lighter blues)
SAP_BRIGHT   = "#4a90d9"   # bright metallic sapphire — hover borders, highlights
SAP_MID      = "#2e6db4"   # mid metallic sapphire — active borders, selected underline
SAP_DIM      = "#1e4a7a"   # dim sapphire — subtle borders

SEL_BG       = "#1e4a7a"   # sapphire selection highlight

# Gold accents — warmer contrast against the cool blue
GOLD         = "#c9a84c"   # primary metallic gold — borders, selected elements
GOLD_BRIGHT  = "#e8c96a"   # bright gold — hover, highlights
GOLD_LIGHT   = "#f0dfa0"   # pale gold — active/selected text
GOLD_DIM     = "#8a6f2e"   # antique gold — secondary labels

FG           = "#d8eaf8"   # cool silver-white — primary text (slight blue tint)
FG_DIM       = "#7a9bbf"   # muted steel-sapphire — secondary text
BORDER       = "#1e3a62"   # sapphire border
BORDER_BRIGHT= "#2e5a8e"   # metallic sapphire border — grid lines, dividers

# Status/grade colors — vivid against the dark blue background
COLOR_GREAT  = "#3eff3e"
COLOR_GOOD   = "#ffd24c"
COLOR_WARN   = "#ff9933"
COLOR_BAD    = "#ff5555"
COLOR_OWNED  = "#6a88aa"
COLOR_NEED   = "#3eff3e"
COLOR_CRAFTED= "#ffd24c"

# ── Short-form aliases (used by tabs) ───────────────────────────────────
# These let every tab do `from theme import BG, FG, DIM, ...` without
# duplicating the palette.
BG      = BG_DEEP        # main window background
DIM     = FG_DIM         # muted/secondary text
SAP     = SAP_BRIGHT     # bright sapphire — the "SAP" most tabs want for highlights
GREEN   = COLOR_GREAT    # success / owned
RED     = COLOR_BAD      # error / missing
ORANGE  = COLOR_WARN     # warning
BG_HDR  = BG_HEADER      # alias used by CREDITS_TAB

WFINFO_STYLESHEET = f"""
/* ── Base ─────────────────────────────────────────────────────────────── */
QWidget {{
    background-color: {BG_DEEP};
    color: {FG};
    font-family: "Segoe UI", "Inter", "Noto Sans", sans-serif;
    font-size: 13px;
    selection-background-color: {SEL_BG};
    selection-color: #ffffff;
}}

/* ── Main window / frames ─────────────────────────────────────────────── */
QMainWindow, QDialog {{
    background-color: {BG_DEEP};
}}
QFrame {{
    background-color: transparent;
}}

/* ── Buttons — gold on sapphire ───────────────────────────────────────── */
QPushButton {{
    background-color: {BG_CARD};
    color: {GOLD};
    border: 1px solid {SAP_MID};
    border-radius: 5px;
    padding: 6px 16px;
    font-weight: 600;
    font-size: 12px;
}}
QPushButton:hover {{
    background-color: {BG_PANEL};
    color: {GOLD_BRIGHT};
    border-color: {SAP_BRIGHT};
    border-top: 1px solid {SAP_BRIGHT};
}}
QPushButton:pressed {{
    background-color: {BG_INPUT};
    color: {GOLD_LIGHT};
    border-color: {GOLD};
}}
QPushButton:disabled {{
    background-color: {BG_PANEL};
    color: {FG_DIM};
    border-color: {BORDER};
}}

/* ── Labels ───────────────────────────────────────────────────────────── */
QLabel {{ background-color: transparent; color: {FG}; }}

/* ── Inputs ───────────────────────────────────────────────────────────── */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {BG_INPUT};
    color: {FG};
    border: 2px solid {SAP_MID};
    border-radius: 5px;
    padding: 5px 8px;
    selection-background-color: {SAP_MID};
    selection-color: #ffffff;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 2px solid {SAP_BRIGHT};
    background-color: {BG_PANEL};
}}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover {{
    border: 2px solid {SAP_BRIGHT};
}}

/* ── ComboBox ─────────────────────────────────────────────────────────── */
QComboBox {{
    background-color: {BG_INPUT};
    color: {FG};
    border: 2px solid {SAP_MID};
    border-radius: 5px;
    padding: 5px 8px;
    padding-right: 26px;
}}
QComboBox:hover {{ border: 2px solid {SAP_BRIGHT}; }}
QComboBox:focus {{ border: 2px solid {SAP_BRIGHT}; }}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 26px;
    border-left: 1px solid {SAP_MID};
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
    background-color: {BG_PANEL};
}}
QComboBox::down-arrow {{
    width: 10px;
    height: 10px;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_CARD};
    color: {FG};
    selection-background-color: {SAP_MID};
    selection-color: #ffffff;
    border: 2px solid {SAP_MID};
    border-radius: 4px;
    outline: 0;
    padding: 2px;
}}

/* ── GroupBox — sapphire border, gold title ───────────────────────────── */
QGroupBox {{
    background-color: {BG_PANEL};
    color: {FG_DIM};
    border: 1px solid {SAP_DIM};
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 12px;
    font-weight: 700;
    font-size: 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: {GOLD};
    background-color: {BG_DEEP};
}}

/* ── CheckBox ─────────────────────────────────────────────────────────── */
QCheckBox {{
    color: {FG};
    spacing: 8px;
    background-color: transparent;
}}
QCheckBox::indicator {{
    width: 15px; height: 15px;
    background-color: {BG_INPUT};
    border: 2px solid {GOLD_DIM};
    border-radius: 3px;
}}
QCheckBox::indicator:checked {{
    background-color: {SAP_MID};
    border: 2px solid {GOLD};
    image: none;
}}
QCheckBox::indicator:hover {{ border-color: {GOLD}; }}
QCheckBox::indicator:checked:hover {{ border-color: {GOLD_BRIGHT}; }}

/* ── Table item checkboxes (QTableWidget UserCheckable items) ─────────── */
QTableWidget::indicator {{
    width: 16px;
    height: 16px;
    border: 2px solid {GOLD_DIM};
    border-radius: 3px;
    background-color: {BG_INPUT};
}}
QTableWidget::indicator:checked {{
    background-color: {SAP_MID};
    border: 2px solid {GOLD};
}}
QTableWidget::indicator:unchecked:hover {{
    border-color: {GOLD};
}}
QTableWidget::indicator:checked:hover {{
    border-color: {GOLD_BRIGHT};
    background-color: {SAP_BRIGHT};
}}

/* ── Tables — sapphire chrome, gold header text ───────────────────────── */
QTableWidget, QTableView {{
    background-color: {BG_PANEL};
    alternate-background-color: {BG_CARD};
    color: {FG};
    gridline-color: {BORDER};
    border: 1px solid {BORDER_BRIGHT};
    border-radius: 6px;
    selection-background-color: {SAP_MID};
    selection-color: #ffffff;
    outline: 0;
}}
/* Hide row number header globally */
QTableWidget QHeaderView:vertical,
QTableView QHeaderView:vertical {{
    width: 0px;
}}
QTableCornerButton::section {{
    background: transparent;
    border: none;
}}

QTableWidget::item, QTableView::item {{
    padding: 4px 8px;
    border: none;
}}
QTableWidget::item:selected, QTableView::item:selected {{
    background-color: {SAP_MID};
    color: #ffffff;
}}
QHeaderView::section {{
    background-color: {BG_HEADER};
    color: {GOLD};
    padding: 6px 10px;
    border: none;
    border-right: 1px solid {SAP_DIM};
    border-bottom: 2px solid {SAP_MID};
    font-weight: 700;
    font-size: 12px;
    letter-spacing: 0.5px;
}}
QHeaderView::section:hover {{
    background-color: {BG_CARD};
    color: {GOLD_BRIGHT};
    border-bottom-color: {SAP_BRIGHT};
}}

/* ── TreeWidget ───────────────────────────────────────────────────────── */
QTreeWidget {{
    background-color: {BG_PANEL};
    alternate-background-color: {BG_CARD};
    color: {FG};
    border: 1px solid {BORDER_BRIGHT};
    border-radius: 6px;
    selection-background-color: {SAP_MID};
    selection-color: #ffffff;
    outline: 0;
}}
QTreeWidget::item {{ padding: 3px 4px; }}
QTreeWidget::item:selected {{
    background-color: {SAP_MID};
    color: #ffffff;
}}
QTreeWidget::branch {{ background-color: transparent; }}

/* ── Tabs — metallic sapphire underline ───────────────────────────────── */
QTabWidget::pane {{
    background-color: {BG_DEEP};
    border: 1px solid {BORDER_BRIGHT};
    border-top: none;
    border-bottom-left-radius: 6px;
    border-bottom-right-radius: 6px;
}}
QTabBar {{
    background-color: {BG_PANEL};
    border-bottom: 2px solid {SAP_MID};
}}
QTabBar::tab {{
    background-color: {BG_PANEL};
    color: {FG_DIM};
    padding: 8px 16px;
    margin-right: 1px;
    border: 1px solid {SAP_DIM};
    border-bottom: none;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    font-weight: 600;
    font-size: 12px;
}}
QTabBar::tab:selected {{
    background-color: {BG_DEEP};
    color: {GOLD_BRIGHT};
    border-color: {SAP_MID};
    border-bottom: 2px solid {BG_DEEP};
    margin-bottom: -1px;
}}
QTabBar::tab:hover:!selected {{
    background-color: {BG_CARD};
    color: {FG};
    border-color: {SAP_BRIGHT};
}}

/* ── ScrollBars — sapphire handles ───────────────────────────────────── */
QScrollBar:vertical {{
    background-color: {BG_PANEL};
    width: 8px;
    border: none;
    border-radius: 4px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background-color: {SAP_DIM};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background-color: {SAP_MID}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background-color: {BG_PANEL};
    height: 8px;
    border: none;
    border-radius: 4px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background-color: {SAP_DIM};
    border-radius: 4px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background-color: {SAP_MID}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── ProgressBar — sapphire to gold gradient ─────────────────────────── */
QProgressBar {{
    background-color: {BG_INPUT};
    border: 1px solid {SAP_DIM};
    border-radius: 4px;
    text-align: center;
    color: {FG};
    height: 14px;
}}
QProgressBar::chunk {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {SAP_MID}, stop:0.6 {SAP_BRIGHT}, stop:1 {GOLD});
    border-radius: 3px;
}}

/* ── Tooltips ─────────────────────────────────────────────────────────── */
QToolTip {{
    background-color: {BG_CARD};
    color: {FG};
    border: 1px solid {SAP_MID};
    padding: 6px 8px;
    border-radius: 5px;
    font-size: 12px;
}}

/* ── Splitter ─────────────────────────────────────────────────────────── */
QSplitter::handle {{ background-color: {SAP_DIM}; width: 2px; height: 2px; }}
QSplitter::handle:hover {{ background-color: {SAP_MID}; }}

/* ── ScrollArea ───────────────────────────────────────────────────────── */
QScrollArea {{ border: none; background-color: transparent; }}
QScrollArea > QWidget > QWidget {{ background-color: transparent; }}

/* ── MessageBox / dialogs ─────────────────────────────────────────────── */
QMessageBox {{ background-color: {BG_DEEP}; }}
QMessageBox QLabel {{ color: {FG}; }}
"""


# ══════════════════════════════════════════════════════════════════════════
# ADDITIONAL THEMES
# Each theme is a function that returns a stylesheet string.
# Based on Warframe's Focus schools for Warframe players who know the lore,
# and designed for color-vision accessibility.
# ══════════════════════════════════════════════════════════════════════════

def _make_stylesheet(bg_deep, bg_panel, bg_card, bg_input, bg_header,
                     accent, accent_bright, accent_dim, accent_hover,
                     sel_bg, fg, fg_dim, border, border_bright,
                     gold, gold_bright, gold_dim,
                     check_checked_bg, check_checked_border):
    """Generate a full stylesheet from palette variables."""
    return f"""
QWidget {{
    background-color: {bg_deep};
    color: {fg};
    font-family: "Segoe UI", "Inter", "Noto Sans", sans-serif;
    font-size: 13px;
    selection-background-color: {sel_bg};
    selection-color: #ffffff;
}}
QMainWindow, QDialog {{ background-color: {bg_deep}; }}
QFrame {{ background-color: transparent; }}
QPushButton {{
    background-color: {bg_card};
    color: {gold};
    border: 1px solid {accent_dim};
    border-radius: 5px;
    padding: 6px 16px;
    font-weight: 600;
    font-size: 12px;
}}
QPushButton:hover {{ background-color: {bg_panel}; color: {gold_bright}; border-color: {accent}; }}
QPushButton:pressed {{ background-color: {bg_input}; color: {fg}; border-color: {gold}; }}
QPushButton:disabled {{ background-color: {bg_panel}; color: {fg_dim}; border-color: {border}; }}
QLabel {{ background-color: transparent; color: {fg}; }}
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {bg_input}; color: {fg};
    border: 2px solid {accent_dim}; border-radius: 5px; padding: 5px 8px;
    selection-background-color: {accent_dim}; selection-color: #ffffff;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{ border: 2px solid {accent}; background-color: {bg_panel}; }}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover {{ border: 2px solid {accent}; }}
QComboBox {{
    background-color: {bg_input}; color: {fg};
    border: 2px solid {accent_dim}; border-radius: 5px; padding: 5px 8px; padding-right: 26px;
}}
QComboBox:hover {{ border: 2px solid {accent}; }}
QComboBox:focus {{ border: 2px solid {accent}; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: top right; width: 26px; border-left: 1px solid {accent_dim}; border-radius: 0 4px 4px 0; background-color: {bg_panel}; }}
QComboBox QAbstractItemView {{ background-color: {bg_card}; color: {fg}; selection-background-color: {sel_bg}; selection-color: #ffffff; border: 2px solid {accent_dim}; border-radius: 4px; outline: 0; padding: 2px; }}
QGroupBox {{ background-color: {bg_panel}; color: {fg_dim}; border: 1px solid {accent_dim}; border-radius: 8px; margin-top: 14px; padding-top: 12px; font-weight: 700; font-size: 12px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 14px; padding: 0 6px; color: {gold}; background-color: {bg_deep}; }}
QCheckBox {{ color: {fg}; spacing: 8px; background-color: transparent; }}
QCheckBox::indicator {{ width: 15px; height: 15px; background-color: {bg_input}; border: 2px solid {gold_dim}; border-radius: 3px; }}
QCheckBox::indicator:checked {{ background-color: {check_checked_bg}; border: 2px solid {check_checked_border}; }}
QCheckBox::indicator:hover {{ border-color: {gold}; }}
QTableWidget, QTableView {{
    background-color: {bg_panel}; alternate-background-color: {bg_card};
    color: {fg}; gridline-color: {border}; border: 1px solid {border_bright};
    border-radius: 6px; selection-background-color: {sel_bg}; selection-color: #ffffff; outline: 0;
}}
QTableWidget::item, QTableView::item {{ padding: 4px 8px; border: none; }}
QTableWidget::item:selected, QTableView::item:selected {{ background-color: {sel_bg}; color: #ffffff; }}
QHeaderView::section {{
    background-color: {bg_header}; color: {gold}; padding: 6px 10px;
    border: none; border-right: 1px solid {border}; border-bottom: 2px solid {accent_dim};
    font-weight: 700; font-size: 12px; letter-spacing: 0.5px;
}}
QHeaderView::section:hover {{ background-color: {bg_card}; color: {gold_bright}; border-bottom-color: {accent}; }}
QTreeWidget {{ background-color: {bg_panel}; alternate-background-color: {bg_card}; color: {fg}; border: 1px solid {border_bright}; border-radius: 6px; selection-background-color: {sel_bg}; selection-color: #ffffff; outline: 0; }}
QTreeWidget::item {{ padding: 3px 4px; }}
QTreeWidget::item:selected {{ background-color: {sel_bg}; color: #ffffff; }}
QTreeWidget::branch {{ background-color: transparent; }}
QTabWidget::pane {{ background-color: {bg_deep}; border: 1px solid {border_bright}; border-top: none; border-radius: 0 0 6px 6px; }}
QTabBar {{ background-color: {bg_panel}; border-bottom: 2px solid {accent_dim}; }}
QTabBar::tab {{ background-color: {bg_panel}; color: {fg_dim}; padding: 8px 16px; margin-right: 1px; border: 1px solid {border}; border-bottom: none; border-radius: 5px 5px 0 0; font-weight: 600; font-size: 12px; }}
QTabBar::tab:selected {{ background-color: {bg_deep}; color: {gold_bright}; border-color: {accent_dim}; border-bottom: 2px solid {bg_deep}; margin-bottom: -1px; }}
QTabBar::tab:hover:!selected {{ background-color: {bg_card}; color: {fg}; border-color: {border_bright}; }}
QScrollBar:vertical {{ background-color: {bg_panel}; width: 8px; border: none; border-radius: 4px; margin: 0; }}
QScrollBar::handle:vertical {{ background-color: {accent_dim}; border-radius: 4px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background-color: {accent}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background-color: {bg_panel}; height: 8px; border: none; border-radius: 4px; margin: 0; }}
QScrollBar::handle:horizontal {{ background-color: {accent_dim}; border-radius: 4px; min-width: 24px; }}
QScrollBar::handle:horizontal:hover {{ background-color: {accent}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QProgressBar {{ background-color: {bg_input}; border: 1px solid {border_bright}; border-radius: 4px; text-align: center; color: {fg}; height: 14px; }}
QProgressBar::chunk {{ background-color: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {accent_dim}, stop:0.6 {accent}, stop:1 {gold}); border-radius: 3px; }}
QToolTip {{ background-color: {bg_card}; color: {fg}; border: 1px solid {accent_dim}; padding: 6px 8px; border-radius: 5px; font-size: 12px; }}
QSplitter::handle {{ background-color: {accent_dim}; width: 2px; height: 2px; }}
QSplitter::handle:hover {{ background-color: {accent}; }}
QScrollArea {{ border: none; background-color: transparent; }}
QScrollArea > QWidget > QWidget {{ background-color: transparent; }}
QMessageBox {{ background-color: {bg_deep}; }}
QMessageBox QLabel {{ color: {fg}; }}
QTableWidget QHeaderView:vertical, QTableView QHeaderView:vertical {{ width: 0px; }}
QTableCornerButton::section {{ background: transparent; border: none; }}
"""


# ── Theme 1: Kieda's Default (sapphire + gold) ────────────────────────────
# Already defined above as WFINFO_STYLESHEET


# ── Theme 2: Madurai (fire red/orange — Deuteranopia safe) ────────────────
# Warframe's Madurai school: offense, red/orange fire energy.
# Colorblind safe: uses orange/amber/cyan instead of red/green pairs.
# Deuteranopes (red-green) distinguish orange vs cyan easily.
THEME_MADURAI = _make_stylesheet(
    bg_deep="#1a0a05",   bg_panel="#2a1208",  bg_card="#3a1a0c",
    bg_input="#150804",  bg_header="#200e07",
    accent="#e85c0d",    accent_bright="#ff8c3a", accent_dim="#b03a00",
    accent_hover="#c04a08",
    sel_bg="#6b2200",
    fg="#f8e8d0",        fg_dim="#c09060",
    border="#3a1808",    border_bright="#6a2a10",
    gold="#f5c842",      gold_bright="#ffe066",  gold_dim="#b08820",
    check_checked_bg="#e85c0d", check_checked_border="#f5c842",
)

# ── Theme 3: Vazarin (deep blue/white — Protanopia safe) ──────────────────
# Warframe's Vazarin school: defense/healing, blue/white water energy.
# Colorblind safe: blue/white spectrum, no reds. Protanopes see blue fine.
# Status colors use cyan (good) vs white (neutral) vs grey (bad).
THEME_VAZARIN = _make_stylesheet(
    bg_deep="#020a1a",   bg_panel="#061428",  bg_card="#0a1e3c",
    bg_input="#041020",  bg_header="#051220",
    accent="#38b6e8",    accent_bright="#6dcfff", accent_dim="#1a7aaa",
    accent_hover="#2090c0",
    sel_bg="#0a3a5c",
    fg="#e8f4ff",        fg_dim="#7ab0d0",
    border="#0a2040",    border_bright="#1a4a70",
    gold="#e0e8f0",      gold_bright="#ffffff",  gold_dim="#8090a0",
    check_checked_bg="#38b6e8", check_checked_border="#ffffff",
)

# ── Theme 4: Naramon (charcoal/white — Tritanopia + universal) ────────────
# Warframe's Naramon school: precision/shadow, near-black with white/silver.
# Colorblind safe for ALL types: pure high-contrast monochrome with
# orange accent (visible to all colorblindness types).
# Also the best accessibility theme for low vision.
THEME_NARAMON = _make_stylesheet(
    bg_deep="#0a0a0a",   bg_panel="#181818",  bg_card="#242424",
    bg_input="#0e0e0e",  bg_header="#141414",
    accent="#e8a020",    accent_bright="#ffbe40", accent_dim="#a06010",
    accent_hover="#c08018",
    sel_bg="#3a2800",
    fg="#f0f0f0",        fg_dim="#909090",
    border="#2a2a2a",    border_bright="#404040",
    gold="#e8a020",      gold_bright="#ffbe40",  gold_dim="#906010",
    check_checked_bg="#e8a020", check_checked_border="#ffbe40",
)

# ── Theme registry ────────────────────────────────────────────────────────
# ── Theme 5: Unairu (stone/earth/desert — Deuteranopia + Protanopia safe) ─
# Warframe's Unairu school: petrification, earth/stone energy, amber/brown tones.
# The deep earth browns avoid all red-green confusion entirely.
# Safe for Deuteranopia and Protanopia — uses amber/tan/sand spectrum only.
THEME_UNAIRU = _make_stylesheet(
    bg_deep="#120d06",   bg_panel="#1e1508",  bg_card="#2a1e0c",
    bg_input="#0e0a04",  bg_header="#181206",
    accent="#c8860a",    accent_bright="#f0a830", accent_dim="#8a5a05",
    accent_hover="#a06808",
    sel_bg="#4a2e00",
    fg="#f0e0c0",        fg_dim="#b09060",
    border="#2e1e08",    border_bright="#5a3810",
    gold="#e8c060",      gold_bright="#ffe888",  gold_dim="#9a7830",
    check_checked_bg="#c8860a", check_checked_border="#e8c060",
)

# ── Theme 6: Zenurik (electricity/energy — Tritanopia safe) ───────────────
# Warframe's Zenurik school: energy manipulation, indigo/electric purple.
# Deep purple base avoids the blue-yellow confusion that affects Tritanopes.
# Uses magenta/violet accents which are visible to all colorblindness types.
THEME_ZENURIK = _make_stylesheet(
    bg_deep="#0d0618",   bg_panel="#180a28",  bg_card="#22103a",
    bg_input="#0a0414",  bg_header="#140820",
    accent="#8a2be2",    accent_bright="#b060ff", accent_dim="#5a1a9a",
    accent_hover="#6a18c0",
    sel_bg="#3a0860",
    fg="#eedcff",        fg_dim="#9060c0",
    border="#28104a",    border_bright="#4a2070",
    gold="#d060e8",      gold_bright="#f090ff",  gold_dim="#8030a0",
    check_checked_bg="#8a2be2", check_checked_border="#d060e8",
)

THEMES = {
    "Kieda's Default": WFINFO_STYLESHEET,
    "Madurai":         THEME_MADURAI,
    "Vazarin":         THEME_VAZARIN,
    "Naramon":         THEME_NARAMON,
    "Unairu":          THEME_UNAIRU,
    "Zenurik":         THEME_ZENURIK,
}

THEME_DESCRIPTIONS = {
    "Kieda's Default": "Sapphire blue + metallic gold — Kieda's signature theme",
    "Madurai":         "Fire red/orange — Deuteranopia safe (red-green colorblind)",
    "Vazarin":         "Deep ocean blue/white — Protanopia safe (red-blind)",
    "Naramon":         "High contrast charcoal/white + amber — safe for ALL colorblindness types",
    "Unairu":          "Earth/stone amber/brown — Deuteranopia + Protanopia safe",
    "Zenurik":         "Electric indigo/violet — Tritanopia safe (blue-yellow colorblind)",
}


def get_theme(name: str) -> str:
    """Return stylesheet for named theme. Falls back to default."""
    return THEMES.get(name, WFINFO_STYLESHEET)


# ── Per-theme palette dicts ───────────────────────────────────────────────
# Each entry maps short name → hex color so tabs can re-apply per-widget
# stylesheets when the theme changes at runtime.
THEME_PALETTES = {
    "Kieda's Default": dict(
        bg=BG_DEEP, bg_panel=BG_PANEL, bg_card=BG_CARD,
        bg_input=BG_INPUT, bg_header=BG_HEADER,
        fg=FG, fg_dim=FG_DIM,
        gold=GOLD, gold_bright=GOLD_BRIGHT,
        accent=SAP_BRIGHT, accent_mid=SAP_MID, accent_dim=SAP_DIM,
        border=BORDER, border_bright=BORDER_BRIGHT,
        green=COLOR_GREAT, red=COLOR_BAD, orange=COLOR_WARN,
    ),
    "Madurai": dict(
        bg="#1a0a05", bg_panel="#2a1208", bg_card="#3a1a0c",
        bg_input="#150804", bg_header="#200e07",
        fg="#f8e8d0", fg_dim="#c09060",
        gold="#f5c842", gold_bright="#ffe066",
        accent="#ff8c3a", accent_mid="#e85c0d", accent_dim="#b03a00",
        border="#3a1808", border_bright="#6a2a10",
        green="#40e0c0", red="#ff6030", orange="#f5c842",
    ),
    "Vazarin": dict(
        bg="#020a1a", bg_panel="#061428", bg_card="#0a1e3c",
        bg_input="#041020", bg_header="#051220",
        fg="#e8f4ff", fg_dim="#7ab0d0",
        gold="#e0e8f0", gold_bright="#ffffff",
        accent="#6dcfff", accent_mid="#38b6e8", accent_dim="#1a7aaa",
        border="#0a2040", border_bright="#1a4a70",
        green="#40e8c0", red="#e890b0", orange="#e0c880",
    ),
    "Naramon": dict(
        bg="#0a0a0a", bg_panel="#181818", bg_card="#242424",
        bg_input="#0e0e0e", bg_header="#141414",
        fg="#f0f0f0", fg_dim="#909090",
        gold="#e8a020", gold_bright="#ffbe40",
        accent="#ffbe40", accent_mid="#e8a020", accent_dim="#a06010",
        border="#2a2a2a", border_bright="#404040",
        green="#e8a020", red="#c0c0c0", orange="#ffbe40",
    ),
    "Unairu": dict(
        bg="#120d06", bg_panel="#1e1508", bg_card="#2a1e0c",
        bg_input="#0e0a04", bg_header="#181206",
        fg="#f0e0c0", fg_dim="#b09060",
        gold="#e8c060", gold_bright="#ffe888",
        accent="#f0a830", accent_mid="#c8860a", accent_dim="#8a5a05",
        border="#2e1e08", border_bright="#5a3810",
        green="#a0c860", red="#e07030", orange="#e8c060",
    ),
    "Zenurik": dict(
        bg="#0d0618", bg_panel="#180a28", bg_card="#22103a",
        bg_input="#0a0414", bg_header="#140820",
        fg="#eedcff", fg_dim="#9060c0",
        gold="#d060e8", gold_bright="#f090ff",
        accent="#b060ff", accent_mid="#8a2be2", accent_dim="#5a1a9a",
        border="#28104a", border_bright="#4a2070",
        green="#60d8b0", red="#e060a0", orange="#d060e8",
    ),
}


def get_palette(name: str = None) -> dict:
    """Return palette dict for named theme (or current saved theme).
    Tabs use this to re-apply per-widget stylesheets on theme change."""
    if name is None:
        name = load_theme()
    return THEME_PALETTES.get(name, THEME_PALETTES["Kieda's Default"])


def save_theme(name: str):
    """Save theme preference to config.json."""
    import json
    config_file = __import__('pathlib').Path(__file__).parent / "config.json"
    try:
        cfg = json.loads(config_file.read_text())
    except Exception:
        cfg = {}
    cfg["theme"] = name
    config_file.write_text(json.dumps(cfg, indent=2))


def load_theme() -> str:
    """Load saved theme name from config.json."""
    import json
    config_file = __import__('pathlib').Path(__file__).parent / "config.json"
    try:
        cfg = json.loads(config_file.read_text())
        return cfg.get("theme", "Kieda's Default")
    except Exception:
        return "Kieda's Default"
