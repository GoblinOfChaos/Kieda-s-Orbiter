# Kieda's Orbiter

A Warframe companion app for **Linux and Windows**. Tracks your inventory, relics, rivens, mastery progress, market prices, and live world state — all in one place.

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
- **Relic Planner** — Plan which relics to run for your most-needed drops (shows owned count, vaulted status)
- **Best Relics** — Which relics give the most value right now
- **Riven Grader** — Grade your rivens against known good rolls; live overlay when you view one in-game
- **Market** — Prime part prices from warframe.market
- **Stats History** — Track your credits, plat, MR, and parts owned over time
- **Equipment** — Mastery status for every weapon, Warframe, and companion category
- **Relic Reward OCR** — Automatic overlay when a relic reward screen appears, showing ownership and platinum value of each reward
- **Six UI themes** — Kieda's Default (sapphire/gold), Madurai, Vazarin, Naramon, Unairu, Zenurik (colorblind-safe options included)

---

## Requirements

| | Linux | Windows |
|---|---|---|
| **Python** | 3.11+ | 3.11+ |
| **Tesseract OCR** | `sudo dnf install tesseract` | [Download](https://github.com/UB-Mannheim/tesseract/wiki) |
| **Rust + Cargo** | Optional — needed to build OCR binary | Optional — needed to build OCR binary |
| **Steam** | Steam + Proton (EE.log auto-detected) | Steam or Epic (EE.log auto-detected) |
| **warframe-api-helper** | Auto-downloaded by installer | Auto-downloaded by installer |

---

## Installation

### Windows — no terminal needed

1. Install **[Python 3.11+](https://python.org/downloads/)** — check **"Add Python to PATH"** during install
2. [**Download ZIP**](https://github.com/GoblinOfChaos/Kiedas-Orbiter/archive/refs/heads/main.zip) and unzip it anywhere
3. Open the folder and double-click **`Install Windows.bat`**
4. After it finishes, find **Kieda's Orbiter** in the **Start Menu**

> If the Start Menu shortcut isn't there yet, double-click **`Start Kieda's Orbiter.bat`** instead.

### Linux

```bash
git clone https://github.com/GoblinOfChaos/Kiedas-Orbiter.git
cd Kiedas-Orbiter
./install.sh
```

After installing, search for **"Kieda's Orbiter"** in your application launcher.

Both installers will:
1. Check Python and Tesseract
2. Create a virtual environment and install PySide6
3. Build the relic reward OCR binary (if Rust is installed)
4. Download the latest Warframe item and price data
5. Download `warframe-api-helper` for your platform
6. Create a start menu entry

On first launch, go to **Status & Tools → File Paths** to verify your EE.log was auto-detected correctly.

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

---

### Keeping data fresh

- **Update Game Data** — refreshes item prices and the item database (~daily)
- **Refresh WFCD Cache** — pulls fresh item data from WFCD GitHub (~weekly)
- **Fetch Live Prices** — gets real-time platinum prices from warframe.market (~5 min)

---

### Linux / Bazzite / KDE Wayland notes

The overlay uses `spectacle` for screen capture via the KDE XDG portal (no focus stealing from Warframe). Always launch from your start menu or a clean terminal — launching from inside VS Code or another Flatpak app will use the wrong DBus session and cause issues.

---

## EE.log location

Auto-detected. Manual override available in **Status & Tools → File Paths**.

| Platform | Default location |
|---|---|
| Linux (Steam/Proton) | `~/.local/share/Steam/steamapps/compatdata/230410/pfx/drive_c/users/steamuser/AppData/Local/Warframe/EE.log` |
| Windows (Steam) | `%LOCALAPPDATA%\Warframe\EE.log` |
| Windows (Epic) | `%LOCALAPPDATA%\Warframe\EE.log` |

---

## Themes

Switch themes in **Status & Tools → UI Theme**. Six themes available:

| Theme | Style | Colorblind safe for |
|---|---|---|
| Kieda's Default | Sapphire blue + gold | — |
| Madurai | Fire red/orange | Deuteranopia |
| Vazarin | Deep navy + cyan | Protanopia |
| Naramon | High-contrast charcoal | All types |
| Unairu | Earth/amber | Deuteranopia + Protanopia |
| Zenurik | Indigo/violet | Tritanopia |

---

## Troubleshooting

### App won't open after a system update (Linux)

If the app stops launching after a Bazzite/Fedora system update, the Python virtual environment may have gotten corrupted or picked up a conflicting Python version. Rebuild it:

```bash
cd ~/wfinfo-ng
rm -rf .venv
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Then relaunch from the start menu. This takes about 2 minutes and fixes most post-update issues.

### Overlay focus steal on KDE Wayland / Bazzite

If the relic reward overlay appears but steals focus from Warframe, the app was likely launched from a Flatpak environment (like VS Code). Always launch from your **start menu** or a clean terminal. Never from inside VS Code.

### Overlay not appearing at all

1. Check **Status & Tools → Live Status** — **Detector** must show "Running"
2. If Detector shows "Not running", click **Reload Detector Config**
3. Check that Tesseract OCR is installed: `tesseract --version`
4. Try pressing **F12** in game to trigger the overlay manually

### Inventory not updating

1. Make sure Warframe is fully loaded (not on launcher/login screen)
2. Click **Refresh Data** in Status & Tools
3. If that doesn't help, travel to a relay and back in-game, then refresh again

---

## Credits

- [knoellle/wfinfo-ng](https://github.com/knoellle/wfinfo-ng) — original Rust OCR engine
- [Sainan/warframe-api-helper](https://github.com/Sainan/warframe-api-helper) — inventory memory scanner (Windows + Linux)
- [WFCD](https://github.com/WFCD) — warframe-items database and warframestat.us API
- [warframe.market](https://warframe.market) — platinum price data
- [Calamity Inc. / Sainan](https://github.com/calamity-inc) — ExportUpgrades, RivenParser
