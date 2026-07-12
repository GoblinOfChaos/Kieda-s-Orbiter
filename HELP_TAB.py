#!/usr/bin/env python3
"""User Guide tab — in-app reference for every tab, button, and overlay."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextBrowser,
)
from theme import BG, BG_CARD, GOLD, FG, DIM, SAP_MID as SAP

GUIDE_MARKDOWN = r"""
# Kieda's Orbiter — User Guide

## Getting started

1. Go to **Status & Tools** and check that **Detector** shows "Running".
2. If EE.log wasn't auto-detected, set it in **Status & Tools → File Paths**.
3. Launch Warframe, then click **Refresh Data** in **Status & Tools** to sync your inventory — most tabs are empty until you do this at least once.

The app is fully usable with Warframe closed for browsing/planning — only **Refresh Data** and the live overlays need the game actually running.

---

## World State

### Dashboard

A live "what's happening in Warframe right now" screen. Pulls public game-state data from the internet every 60 seconds — **works even with Warframe closed**, since it's not reading anything from your game.

Shows: day/night **Cycles** for Earth, Cetus, Orb Vallis, Cambion Drift, and Duviri; **Void Fissures** grouped by relic era with mission/node/time-left (Steel Path and Void Storm fissures are marked); **Sortie** and **Archon Hunt** with their timers and mission variants; **Arbitration**; whether **Baro Ki'Teer** is here (with his stock and prices) or his ETA if not; the current **Steel Path** weekly reward; and active **Nightwave** challenges.

- The **↻ button** (top-right) forces an immediate refresh instead of waiting for the 60-second timer.
- Everything else is read-only.

**Note:** Nightwave's "completed" checkmarks reflect the public API's own tracking, not necessarily your personal progress. If the internet fetch fails, the Dashboard falls back to the last successful copy and shows an error at the top rather than going blank.

---

## Inventory

### Inventory

A searchable table of every prime part and equipment component you own, with counts.

- **Search box** — filters live as you type.
- **Hide zero-count items** — hides everything you own none of (owned-zero rows are shown greyed out otherwise).
- Click any column header to sort; column widths are remembered between sessions.

**Note:** this only updates when you click **Refresh Data** on Status & Tools — it reads a saved file, it doesn't watch the game live.

### Foundry

Every craftable Prime item, what parts it needs, and whether you can build it right now.

- **Search box** — filter by equipment name.
- **Only show missing/not craftable** — hides anything you can already fully build.

### Missing Parts

The heart of the app: every Prime part you currently **NEED** — meaning you own zero and have never crafted it before — with its plat/ducat value and exactly which relics drop it.

- **Search box**, **Era dropdown** (Any/Lith/Meso/Neo/Axi/Vanguard), **Type dropdown** — narrow the list down.
- **Relics dropdown** (All / Non-vaulted only) — hide parts that only drop from vaulted relics you can't farm normally.
- **Hide crafted-before** — hides parts you've marked (or the app auto-detected) as previously built.
- **Have relics only** — only show parts where you currently own at least one relic that drops them.
- **Crafted checkboxes** — click to mark a part as "crafted before" yourself; this is saved. Some rows are already checked and greyed out — those were detected automatically because you own or have mastered the finished item, so you can't un-check them here.
- **Click a part's name** — opens a popup listing every relic that drops it.
- **Click a relic name** in the Drops From column — opens a detailed relic popup with rarity breakdown, your ownership, and expected plat value.

**Color key** (shown at the bottom of the tab): green dot = you own that relic; yellow dot = it's farmable but you don't own it; red dot = it's vaulted and you need it. (R)/(U)/(C) after a drop name = Rare/Uncommon/Common.

### Set Progress

Tracks completion of every full Prime **set** (the whole Warframe/weapon, not one part at a time) with a progress bar.

- **Search box**
- **Show dropdown** — All / Incomplete only / Almost done (≥75%) / Just started (≤25%) / Complete only.

### Mod Collection

Every mod in the game, cross-referenced with what you own, including where to farm the ones you're missing.

- **Search box** — matches name, type, source, or drop location.
- **Hide owned mods** — only show mods you own zero of.
- Columns are sortable.

### Mastery Helper

Helps you decide what to level up for Mastery Rank, split into three sub-tabs:

- **Easy (own now)** — things you already own that aren't rank 30 yet; free MR. Green background = rank 25+ (nearly there), yellow = rank 15+.
- **From Relics** — never-leveled Prime items where at least one missing part drops from a relic you already own. Green = every missing part is coverable from what you own, yellow = some of it is.
- **Never Owned** — items you've never leveled at all, sorted cheapest-to-acquire first. Green = free to complete, yellow = under 50p.

Each sub-tab has a **Type filter dropdown**, and a summary bar up top shows your current MR plus counts for each category.

**Note:** entirely derived from your last **Refresh Data** — it's only as current as your last sync.

---

## Collectibles

### Ayatan Sculptures

All 12 sculptures with owned counts (summed across empty/partially/fully-filled copies) and drop locations.

- **Search box**, **Hide owned sculptures** checkbox.

### Conservation Tags

All 54 wildlife conservation tags with owned counts.

- **Search box**, **Hide owned tags** checkbox.

### Emblems

All 26 clan/alliance/event emblems with owned status (Yes/No - these aren't stackable).

- **Search box**, **Hide owned emblems** checkbox.

### Ephemera

All 98 cosmetic ephemera with owned status and drop locations.

- **Search box**, **Hide owned ephemera** checkbox.

### Captura Scenes

All 201 backdrop scenes with owned counts.

- **Search box**, **Hide owned scenes** checkbox.

### Glyphs

All 1668 profile/chat glyphs with owned status (Yes/No - these aren't stackable).

- **Search box**, **Hide owned glyphs** checkbox.

---

## Relics

### Relic Planner

A three-panel tool: build a custom "shopping list" of parts you want, and it tells you which relics to crack.

- **Left panel** — search every Prime part in the game; double-click one to add it to your list.
- **Middle panel (your list)** — **Remove** deletes the selected part, **Clear** empties the whole list. **Add All Missing Parts** adds everything you currently own zero of. **Add Never Obtained** adds only parts you've truly never owned or crafted (excludes anything you've built before and later used up).
- **Right panel** — matching relics, ranked by how many of your list's parts they drop. **Show owned relics only** restricts this to relics you currently have. Green-tinted rows = you own that relic; red-tinted = vaulted and unowned.

### Best Relics

Ranks every relic by expected platinum value **specifically toward your own need list** — i.e. "which relics are most worth cracking for me right now," not general value.

- **Era dropdown**, **Show dropdown** (Non-vaulted only / All relics), **Owned only checkbox**.
- **Double-click a row** for the full drop-table popup (rarity, ownership, expected value).

**Note:** the expected-value numbers assume opening the relic solo at Intact refinement — they don't account for squad bonuses or higher refinement.

---

## Rivens

### Riven Grader

Every riven you own, automatically graded, plus a "good roll" reference for any weapon.

- **Look up weapon** (top bar) — search any weapon to see its good-roll guide, even without owning a riven for it.
- **Your Rivens table (left)** — Grade is color-coded (green = GREAT, gold = GOOD, orange = OK, red = WEAK/REROLL); **filter box** searches by weapon or stat text; click a row to see its full detail on the right.
- **Detail panel (right)** — shows the "good combo" guide for the selected weapon, with your riven's actual rolled stats matched against it (green highlight = you have that stat).

**Note:** rivens are graded automatically in the background every 5 minutes while Warframe is running — there's nothing to click to trigger grading itself, this tab just displays the results.

---

## Market

### Market

A general price-sheet of Prime parts with known plat prices (not tied to your personal need list).

- **Search box**, **Min plat** numeric filter, **Owned items only** checkbox, **Hide 0p items** checkbox (on by default).
- Plat column color-codes green (≥20p) and yellow (≥5p); Owned column highlights blue if you own any.

**Note:** this tab has no refresh button of its own — prices come from **Update Game Data** / **Fetch Live Prices** on Status & Tools.

### Stats History

A timeline of your credits, plat, mastery rank, and prime-part progress over time, recorded automatically.

- **↻ Refresh button** — reload from disk.
- **Show last dropdown** — All time / Last 7 days / Last 30 days / Last 24 hours.
- Table shows one row per snapshot, with change (Δ) columns colored green (increase) or red (decrease).

**Note:** snapshots are recorded automatically every 5 minutes while Warframe is running — nothing to click to start it, just play and check back.

---

## Equipment

### Arcanes

Every arcane in the game (Warframe, Melee, Primary, Secondary, Operator, Amp, Zaw, Kitgun, Bow, and Shotgun arcanes), with owned counts and drop locations. Lives here rather than under Inventory since arcanes directly affect specific weapons/Warframes, same as the rest of this section.

- **Search box**, **Type dropdown**, **Hide owned arcanes** checkbox.
- Owned counts are highlighted; columns are sortable.

### Warframe / Primary / Secondary / Melee / Archwing / Necramech / Sentinel / Sentinel Weapon / Pet

Nine near-identical tabs — each a tree of every item in that category, whether you've mastered it, and what you still need.

- Header shows Total / Mastered / Missing counts for that category.
- **Show only missing** — hides mastered items.
- **Expand all / Collapse all** — for the whole tree at once; clicking a row also toggles it individually.
- **Wiki** link (rightmost column) — opens that item's wiki page in your browser.
- A 🔧 badge next to an item's name means it's itself required to craft something else — hover it to see what.
- Tree structure: item → components (with quantity needed) → drop sources (location, rarity, drop chance, rotation).
- The **Warframe** tab has an extra **Subsumed** column showing which frames you've fed to Helminth.

**Note:** these tabs need at least one **Refresh Data** run (with Warframe running) before they have anything to show.

---

## System

### Status & Tools

The control center: live status, data-refresh actions, overlay settings, file paths, theme, update checker, and logs.

**Live Status panel** (auto-refreshes every 2 seconds):
- **Warframe** — green "Running" / grey "Not running", detected by checking for the game's process.
- **Detector** — whether the background OCR watcher (the part that watches for relic reward screens) is running.
- **Overlay** — whether the popup overlay process is currently running.
- **Last refresh** — how long since your inventory was last synced.
- **Items in db** — total tracked items, NEED vs. owned.
- **Last detection** — the last relic reward the OCR actually read, or "(none yet)".

**Actions:**
- **Refresh Data** — the main sync button. Reads your live inventory from Warframe (via `warframe-api-helper`) and rebuilds everything derived from it (Missing Parts, Set Progress, Equipment, stats snapshot). **Requires Warframe to be running** — you'll get a warning dialog if it's not. Every other open tab reloads automatically when this finishes, no restart needed.
  **Performance note:** `warframe-api-helper` caches your auth token after the first successful read, so most refreshes are a fast, stutter-free network call. But if that cached token has expired (or this is your first refresh), it has to fall back to scanning the game's live memory to find a fresh one — this can cause a brief in-game stutter, typically a couple seconds. It's a one-time cost per token, not something that happens every refresh.
- **Update Game Data** — refreshes item prices and the item list from the public Warframe API. Safe to run anytime.
- **Refresh WFCD Cache** — force-downloads a fresh (~40MB) item database from WFCD's GitHub. Rarely needed by itself.
- **Fetch Live Prices** — pulls real platinum prices from warframe.market. Takes a few minutes (rate-limited).
- **Clear Cache** — deletes the local item-database cache file directly; it'll re-download next time something needs it.
- **Restart Overlay** — kills and relaunches the popup overlay process; useful if it stops responding.
- **Test Overlay** — pops up the reward overlay immediately with 4 sample fake items, so you can check its appearance/position without waiting for a real relic detection.
- **Reload Detector Config** — restarts the background OCR detector so it picks up changes you made in Advanced Settings.
- **Rebuild API Helper** — a developer-only option for building `warframe-api-helper` from source; shows an informational message instead of doing anything if you're on a normal install (which everyone is by default — the installer downloads a ready-made copy).

**Overlay Display:**
- **Display on dropdown** — which monitor the reward overlay first appears on ("Auto" follows the Warframe window). You can still drag it anywhere afterward — this just sets the starting spot.
- **Apply & Reset Position** — saves your monitor choice and clears any remembered drag position, so the overlay snaps back to the default spot next time. Restart the overlay afterward for it to take effect.
- **Reset Position Only** — clears the remembered position without touching the monitor setting.

**Tip:** normally you don't need either button — just drag the popup wherever you like during a real detection, and it remembers that spot automatically.

**File Paths:**
- **EE.log** and **inventory.json** — leave blank to auto-detect, or use **Browse** to point at a non-standard location. A ✓/✗ label shows whether the currently-effective path actually exists.
- **Save Paths** — writes any overrides you set.

**UI Theme:**
- Pick a theme from the dropdown and click **Apply** (scrolling the dropdown does nothing on purpose, to avoid accidentally changing themes while scrolling the page).
- A reference table below explains each theme's colorblindness safety.

**Updates:**
- **Check for Updates** — checks GitHub for a newer app version and PyPI for a newer PySide6, in the background (can take up to ~15 seconds).
- The app also checks for a newer version automatically on startup, in the background — if one's available, a popup shows the version numbers, a link to the release, and quick update instructions. No popup if you're already up to date.

**Advanced Settings** (collapsed by default — only change these if you know what you're doing): trigger pattern, desktop notifications toggle, Warframe window name, pre-capture delay, poll interval, overlay display duration, and a duplicate EE.log path field, all backed by `config.json`. **Save settings** / **Reload from disk** buttons.

**Output Log:** toggle between **Overlay Log** (live-tailing `overlay.log`) and **Command Output** (the result of whichever Action button you last ran).

**Note:** only one Action button can run at a time — trying to run a second one while another is busy shows a warning instead of queuing it.

### Credits

A read-only thank-you page listing every open-source project, data source, and person the app depends on, with clickable links to each.

### User Guide

This tab. If you're reading this, you found it.

---

## The overlays, explained

There are three separate popup windows that can appear while you're playing, all frameless, semi-transparent, always-on-top, and **draggable** — left-click and drag to reposition any of them, and that position is remembered automatically for next time.

**Relic reward overlay** — appears after cracking a relic, showing up to 4 rewards with ownership status:
- **NEED** (green) — you've never had this, prioritize it.
- **OWNED** (blue-grey, with count) — you already have copies.
- **CRAFTED** (gold) — you've built the finished item before.
- **UNKNOWN** (red) — the OCR couldn't read the text clearly.

It appears a couple seconds after the reward screen (time to capture and read the screen) and auto-hides after 30 seconds by default (adjustable in Advanced Settings). It's built to avoid stealing keyboard/mouse focus from the game.

**Relic recommendation overlay** — a separate small popup at the relic-selection screen before a Void Fissure mission, showing your best relics to run ranked by expected value toward your need list. Auto-hides after 60 seconds as a safety net, or immediately once you pick a relic.

**Riven grading overlay** — appears while you're at the Arsenal, showing every graded riven you own with a colored border by grade. If you just rerolled one, it shows a "↻ REROLLED" badge with the old stats struck through above the new ones. Has its own small close button, and fades out automatically 2 minutes after your last inventory update.
"""


class HelpTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("User Guide")
        title.setStyleSheet(
            f"color: {GOLD}; font-size: 18px; font-weight: 700; "
            f"letter-spacing: 1px; background: transparent;"
        )
        layout.addWidget(title)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Find:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Type to jump to the next match (Enter to repeat)")
        self._search.returnPressed.connect(self._find_next)
        search_row.addWidget(self._search)
        layout.addLayout(search_row)

        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        self._browser.setStyleSheet(
            f"QTextBrowser {{ background: {BG_CARD}; color: {FG}; border: 1px solid #1e3a62; "
            f"border-radius: 6px; padding: 10px; font-size: 13px; }}"
        )
        self._browser.setMarkdown(GUIDE_MARKDOWN)
        layout.addWidget(self._browser, stretch=1)

    def _find_next(self):
        query = self._search.text().strip()
        if not query:
            return
        if not self._browser.find(query):
            # Wrap around: jump back to the top and try again
            self._browser.moveCursor(self._browser.textCursor().Start)
            self._browser.find(query)
