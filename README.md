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
- **Missing Mods** — Mods you haven't acquired yet
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

- **Launch**: Run `./control-panel.sh` or use the desktop entry (if installed)
- **Inventory**: Run Warframe with `warframe-api-helper` active, then click **Refresh Data**
- **Relic reward overlay**: The `orbiter` binary watches EE.log and pops up automatically. Press **F12** to trigger manually
- **Riven overlay**: Opens automatically when you view a riven mod in-game

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
