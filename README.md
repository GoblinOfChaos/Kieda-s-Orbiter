# Kieda's Orbiter

A Linux Warframe companion app. Tracks your inventory, relics, rivens, mastery progress, market prices, and live world state — all in one place.

Built on top of [wfinfo-ng](https://github.com/knoellle/wfinfo-ng) by knoellle, with a full PySide6 GUI and many additional features.

---

## Features

- **Dashboard** — Live world state: void fissures, sortie, arbitration, Baro Ki'Teer, day/night cycles, Nightwave, Steel Path
- **Inventory** — Browse everything you own, with ownership status
- **Missing Parts** — What prime parts you still need, and which relics drop them
- **Set Progress** — Track completion % of every prime set
- **Foundry** — Items in progress or ready to claim
- **Mod Collection** — All mods with owned counts; filter to show only missing ones
- **Mastery Helper** — Items to level for free MR XP, sourced from your own relics
- **Relic Planner** — Plan which relics to run for your most-needed drops
- **Best Relics** — Which relics give the most value right now
- **Riven Grader** — Grade your rivens against known good rolls; live overlay when you view one in-game
- **Market** — Prime part prices from warframe.market
- **Stats History** — Track your credits, plat, MR, and parts owned over time
- **Equipment** — Mastery status for every weapon, Warframe, and companion category
- **Relic Reward OCR** — Automatic overlay when a relic reward screen appears, showing ownership and platinum value of each reward
- **Six UI themes** — Kieda's Default (sapphire/gold), Madurai, Vazarin, Naramon, Unairu, Zenurik (colorblind-safe options included)

---

## Requirements

- **Linux** (Windows support planned)
- **Python 3.11+**
- **PySide6** — installed automatically via pip
- **Tesseract OCR** — for the relic reward overlay (`sudo apt install tesseract-ocr` / `sudo dnf install tesseract`)
- **Rust + Cargo** — only needed to build the OCR detector binary ([rustup.rs](https://rustup.rs))
- **Steam + Proton** — Warframe must be run through Steam (EE.log is auto-detected)
- **warframe-api-helper** — included binary for inventory reading (Linux x86-64)

---

## Installation

```bash
git clone https://github.com/GoblinOfChaos/Kieda-s-Orbiter.git
cd Kieda-s-Orbiter
./install.sh
```

That's it. The installer will:
1. Check for Python 3.11+ and Tesseract OCR
2. Create a Python virtual environment and install dependencies
3. Build the relic reward OCR binary (if Rust is installed)
4. Download the latest Warframe item and price data
5. Install the app icon and **add it to your start menu**

After installing, search for **"Kieda's Orbiter"** in your start menu (or application launcher) to launch it.

On first launch, go to **Status & Tools → File Paths** to verify your EE.log was auto-detected correctly.

### Manual steps (if you prefer)

<details>
<summary>Expand for manual installation steps</summary>

```bash
# Create virtual environment
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# (Optional) Build the relic reward OCR detector — requires Rust
cargo build --release --bin orbiter

# Download Warframe data
./update.sh

# Install icon + start menu entry
mkdir -p ~/.local/share/icons/hicolor/scalable/apps
cp orbiter.svg ~/.local/share/icons/hicolor/scalable/apps/
cp kiedas-orbiter.desktop ~/.local/share/applications/
update-desktop-database ~/.local/share/applications/

# Launch
./control-panel.sh
```

</details>

---

## Usage

### Getting started

1. Launch the app from your start menu (search "Kieda's Orbiter")
2. Go to **Status & Tools** and check that **Detector** shows "Running"
3. If EE.log wasn't auto-detected, set it in **Status & Tools → File Paths**
4. Click **Refresh Data** after running Warframe to sync your inventory

---

### Relic reward overlay

When you crack a relic, the overlay pops up automatically showing each reward with your ownership status:

- 🟢 **NEED** — you've never had this part, take it
- 🔵 **OWNED x2** — you already have copies
- 🟡 **CRAFTED** — you've built/mastered this before

**Tips:**
- The overlay appears ~2-3 seconds after the reward screen — it needs time to capture and process
- **Drag it** anywhere on screen — position is remembered between sessions
- Press **F12** to trigger it manually (useful for testing)
- Change which monitor it appears on in **Status & Tools → Overlay Display**
- Adjust how long it stays visible in **Status & Tools → Advanced Settings → Overlay display duration**

---

### Inventory sync

Inventory data comes from `warframe-api-helper` which reads your game memory:

1. Launch Warframe and get to the main orbiter
2. The helper reads your inventory automatically in the background
3. Click **Refresh Data** in **Status & Tools** to rebuild all derived data
4. All tabs (Missing Parts, Relic Planner, etc.) update immediately

---

### Relic Planner

1. Click **Add All Missing Parts** or **Add Never Obtained** to populate your need list
2. The right panel shows relics ranked by how many of your needed parts they drop
3. Green rows = relics you already own, red = vaulted, normal = unvaulted but unowned
4. Check **Show owned relics only** to filter to just what you can run right now
5. Double-click a part in the left panel to add it individually

---

### Riven Grader

The riven overlay appears automatically when you view a riven in your Arsenal. It shows:
- Grade (Great / Good / OK / Weak / Reroll)
- Stats comparison if you just rerolled
- All your rivens ranked by quality

The grader uses roll data from `riven_good_rolls.json` — you can edit this file to customise what counts as a good roll for each weapon.

---

### Keeping data fresh

- **Update Game Data** — refreshes item prices and the item database (~daily)
- **Refresh WFCD Cache** — pulls fresh item data from WFCD GitHub (~weekly)
- **Fetch Live Prices** — gets real-time platinum prices from warframe.market (takes ~5 min due to rate limits)

---

### Bazzite / KDE Wayland notes

The overlay uses `spectacle` for screen capture via the KDE XDG portal. If the overlay appears but focus is lost from Warframe, this usually means the app was launched from a Flatpak environment (like VS Code). Always launch from your start menu or a clean terminal, not from inside VS Code.

---

## EE.log location

Auto-detected for most Steam/Proton setups. Manual path can be set in **Status & Tools → File Paths**. Default location:

```
~/.local/share/Steam/steamapps/compatdata/230410/pfx/drive_c/users/steamuser/AppData/Local/Warframe/EE.log
```

---

## Themes

Switch themes in **Status & Tools → UI Theme**. Six themes available, including colorblind-safe options based on Warframe's Focus schools:

| Theme | Style | Colorblind safe for |
|---|---|---|
| Kieda's Default | Sapphire blue + gold | — |
| Madurai | Fire red/orange | Deuteranopia |
| Vazarin | Deep navy + cyan | Protanopia |
| Naramon | High-contrast charcoal | All types |
| Unairu | Earth/amber | Deuteranopia + Protanopia |
| Zenurik | Indigo/violet | Tritanopia |

---

## Credits

- [knoellle/wfinfo-ng](https://github.com/knoellle/wfinfo-ng) — original Rust OCR engine
- [WFCD](https://github.com/WFCD) — warframe-items database and warframestat.us API
- [warframe.market](https://warframe.market) — platinum price data
- [Calamity Inc. / Sainan](https://github.com/calamity-inc) — ExportUpgrades, RivenParser
