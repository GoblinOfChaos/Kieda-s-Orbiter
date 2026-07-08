# Windows Full Support — AI Handoff Document

## Project

**Kieda's Orbiter** — A Linux + Windows Warframe companion app (inventory, relics, rivens, market, relic reward OCR overlay).

- **GitHub:** https://github.com/GoblinOfChaos/Kieda-s-Orbiter
- **Current version:** v1.2.1
- **Language:** Python (PySide6 GUI) + Rust (OCR detector binary)
- **Owner:** GoblinOfChaos — complete beginner, never edit files manually, always make changes directly

---

## Current Windows State

The Python GUI app is **fully cross-platform** and should work on Windows as-is. The installer infrastructure is in place. What's **not yet done** is building and distributing the Rust OCR binary for Windows so users don't need Rust installed.

### What works on Windows right now
- All Python tabs (Dashboard, Inventory, Relic Planner, Riven Grader, Market, etc.)
- EE.log auto-detection (`%LOCALAPPDATA%\Warframe\EE.log` + Steam registry + Epic)
- `warframe-api-helper.exe` auto-downloaded by `download_helper.py`
- Double-click `Install Windows.bat` → runs `install.py` → creates Start Menu entry
- Cross-platform process management via `platform_utils.py` (psutil)
- `launcher.py` replaces all shell scripts

### What's broken / missing on Windows
1. **Rust OCR binary not pre-built for Windows** — users currently have to install Rust and build it themselves, which is impractical. The binary (`target/release/orbiter.exe`) needs to be built in CI and attached to GitHub Releases.
2. **`install.py` doesn't download the Rust binary** — it only downloads `warframe-api-helper`. After the CI builds the binary, `download_helper.py` should also download `orbiter.exe`.
3. **`warframe-watcher.py` uses hardcoded Linux paths** for the binary — it uses `target/release/orbiter` (no `.exe`). The `IS_WINDOWS` check in `platform_utils.py` handles this but `WFINFO_BIN` in `warframe-watcher.py` may need updating.

---

## Key Files to Know

```
launcher.py          — Cross-platform launcher (app/overlay/detector/watcher)
platform_utils.py    — psutil-based process management (is_running, kill_processes, etc.)
install.py           — Cross-platform Python installer
download_helper.py   — Downloads warframe-api-helper from Sainan's GitHub releases
update.py            — Downloads Warframe item/price data (replaces update.sh)
warframe-watcher.py  — Watches for Warframe process, restarts the detector
overlay.py           — Relic reward overlay (Qt window)
paths.py             — All file path resolution, DATA_DIR/CACHE_DIR cross-platform
src/bin/main.rs      — Rust OCR detector binary source
```

---

## Task 1: GitHub Actions — Build Rust Binary for Windows + Linux

Create `.github/workflows/release.yml` that triggers on tag push (`v*`), builds the `orbiter` binary for both platforms, and attaches to the GitHub Release.

### Linux build notes
- Needs: `libtesseract-dev libleptonica-dev xorg-dev libxcb-* libxi-dev libxtst-dev libdbus-1-dev pkg-config fontconfig-devel openssl-devel`
- Ubuntu `ubuntu-latest` runner has these available via apt
- The binary dynamically links against `libtesseract.so.5.5` — either link statically or bundle the lib
- Rust toolchain pinned to `1.96.0` via `rust-toolchain.toml`

### Windows build notes
- `windows-latest` runner
- Needs Tesseract on Windows — install via `choco install tesseract` or use vcpkg
- `xcap` on Windows uses GDI/DXGI (already coded with `#[cfg(target_os = "windows")]`)
- The screenshot path on Windows uses `xcap::Monitor` directly, no spectacle needed
- `notify-send` is called but blocked via `config.json show_notifications=0` — on Windows this call will fail gracefully (notify-send doesn't exist)

### Suggested workflow structure

```yaml
name: Release
on:
  push:
    tags: ['v*']

jobs:
  build-linux:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@master
        with:
          toolchain: "1.96.0"
      - name: Install deps
        run: sudo apt-get install -y libtesseract-dev libleptonica-dev xorg-dev ...
      - name: Build
        run: cargo build --release --bin orbiter
      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: orbiter-linux
          path: target/release/orbiter

  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@master
        with:
          toolchain: "1.96.0"
      - name: Install Tesseract
        run: choco install tesseract  # or use vcpkg
      - name: Build
        run: cargo build --release --bin orbiter
      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: orbiter-windows
          path: target/release/orbiter.exe

  release:
    needs: [build-linux, build-windows]
    runs-on: ubuntu-latest
    steps:
      - download both artifacts
      - attach to GitHub Release via gh CLI or actions/create-release
```

---

## Task 2: Update `download_helper.py` to Also Download the Orbiter Binary

After CI is set up and a release with binaries exists, extend `download_helper.py` to also download `orbiter` / `orbiter.exe` from the GitHub Release assets.

The release assets would be named something like:
- `orbiter-linux-x86_64` 
- `orbiter-windows-x86_64.exe`

`download_helper.py` already has the pattern for this (it downloads `warframe-api-helper.exe`). Add a parallel function `download_orbiter()` and call it from `install.py` and `install.sh`.

**`install.py`** already has a step for building Rust — replace the build step with a download step when a pre-built binary is available.

---

## Task 3: Test on Real Windows Machine

Before declaring Windows fully supported:
1. Clone repo on a fresh Windows 11 machine with Python 3.11+ installed
2. Double-click `Install Windows.bat`
3. Verify Start Menu shortcut appears
4. Launch app, check all tabs load
5. Run Warframe, verify EE.log is auto-detected
6. Crack a relic, verify OCR overlay appears without stealing focus
7. Click Refresh Data, verify inventory syncs

Known potential issues to watch for:
- `QT_QPA_PLATFORM` — on Windows this should be unset (Qt auto-detects)
- `LD_LIBRARY_PATH` — Windows uses PATH, not LD_LIBRARY_PATH (handled in `launcher.py`)
- `warframe-watcher.py` uses `os.getuid()` which doesn't exist on Windows — the `clean_env_for_launch()` function in `platform_utils.py` guards this with `IS_LINUX or IS_MAC` but verify
- The overlay window flags (`X11BypassWindowManagerHint`) are X11-specific — on Windows they're ignored, which is fine, but verify the overlay actually appears

---

## Task 4: Fix notify-send on Windows

The Rust binary calls `notify-send` which doesn't exist on Windows. The code already has a `show_notifications` config check, but on Windows the `Command::new("notify-send")` call will fail with "program not found". This should already be handled gracefully (the `spawn()` result is ignored with `let _ =`) but verify in the Rust binary at `src/ownership.rs`:

```rust
pub fn notify(title: &str, body: &str, urgency: &str) {
    let _ = Command::new("notify-send")  // ← this silently fails on Windows, which is fine
        ...
```

If it causes any issues on Windows, add `#[cfg(not(target_os = "windows"))]` to the function.

---

## Repo Structure Quick Reference

```
Install Windows.bat    — User double-clicks this to install on Windows
Start Kieda's Orbiter.bat — User double-clicks to launch
install.py             — Python installer (called by the .bat)
launcher.py            — python launcher.py [app|overlay|detector|watcher]
platform_utils.py      — Cross-platform process utilities
download_helper.py     — Downloads warframe-api-helper + (future) orbiter binary
update.py              — Downloads prices.json + filtered_items.json
warframe-watcher.py    — Daemon: watches for Warframe, restarts detector
overlay.py             — Relic reward overlay (floating Qt window)
riven_grader_overlay.py — Riven grader overlay
missing-parts.py       — Main GUI entry point
paths.py               — All file paths (DATA_DIR, CACHE_DIR, EE.log detection)
src/bin/main.rs        — Rust OCR detector (reads EE.log, screenshots, writes state file)
src/ownership.rs       — Ownership lookup + notify-send call
rust-toolchain.toml    — Pins Rust to 1.96.0
```

---

## Important Notes

- **Owner is a complete beginner** — never tell them to edit files manually, always make all changes directly
- **Linux is working** — don't break the Linux flow when adding Windows support
- **The overlay's focus-steal fix** is Linux/Bazzite-specific (spectacle via KDE portal). On Windows, xcap::Monitor is used instead and focus stealing shouldn't be an issue since Windows handles overlay windows differently
- **The venv must be Python 3.13 only** — having multiple Python versions in the venv causes Qt lib conflicts. `install.py` creates the venv with `sys.executable`, which should be fine as long as the user has one Python installed
- **DBus / host env setup** in `launcher.py` and `platform_utils.py` only runs on Linux — Windows branch is clean

---

## How to Test the Overlay on Windows (without Warframe)

```python
# In a terminal, run:
python launcher.py overlay

# Then trigger a fake detection:
python -c "
import json, time, sys
sys.path.insert(0, '.')
from paths import DATA_DIR
state = {
    'timestamp': int(time.time()),
    'warframe': {'x': 0, 'y': 0, 'width': 1920, 'height': 1080},
    'rewards': [
        {'name': 'Rhino Prime Chassis', 'status': 'NEED', 'count': 0},
        {'name': 'Forma Blueprint', 'status': 'OWNED', 'count': 5},
    ]
}
(DATA_DIR / 'latest-detection.json').write_text(json.dumps(state))
print('Overlay should pop up')
"
```
