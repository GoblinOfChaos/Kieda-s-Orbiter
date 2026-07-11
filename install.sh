#!/usr/bin/env bash
# install.sh — Kieda's Orbiter installer
# Run this once after cloning the repo. Re-running it is safe.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="Kieda's Orbiter"
DESKTOP_ID="kiedas-orbiter"

# ── Colours ───────────────────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}▶${RESET}  $*"; }
success() { echo -e "${GREEN}✓${RESET}  $*"; }
warn()    { echo -e "${YELLOW}!${RESET}  $*"; }
fail()    { echo -e "${RED}✗${RESET}  $*"; exit 1; }
section() { echo; echo -e "${BOLD}── $* ──────────────────────────────────${RESET}"; }

echo
echo -e "${BOLD}${CYAN}Kieda's Orbiter — Installer${RESET}"
echo "Installing into: $REPO_DIR"
echo

# ── 1. Check Python ───────────────────────────────────────────────────────
section "Python"

PYTHON=""
for cmd in python3.13 python3.12 python3.11 python3; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" -c "import sys; print(sys.version_info[:2])")
        if "$cmd" -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" 2>/dev/null; then
            PYTHON="$cmd"
            success "Found $cmd ($ver)"
            break
        else
            warn "$cmd found but version $ver is too old (need 3.11+)"
        fi
    fi
done

[[ -z "$PYTHON" ]] && fail "Python 3.11+ is required. Install it with your package manager:
  Fedora/RHEL:  sudo dnf install python3
  Debian/Ubuntu: sudo apt install python3
  Arch:         sudo pacman -S python"

# ── 2. Check Tesseract (needed for relic reward overlay) ──────────────────
section "Tesseract OCR"

if command -v tesseract &>/dev/null; then
    success "tesseract found ($(tesseract --version 2>&1 | head -1))"
else
    warn "tesseract not found — the relic reward overlay won't work without it."
    warn "Install with:"
    warn "  Fedora/RHEL:   sudo dnf install tesseract"
    warn "  Debian/Ubuntu: sudo apt install tesseract-ocr"
    warn "  Arch:          sudo pacman -S tesseract"
    warn "Continuing anyway — all other features will work fine."
fi

# ── 3. Create virtual environment ─────────────────────────────────────────
section "Python environment"

if [[ ! -d "$REPO_DIR/.venv" ]]; then
    info "Creating virtual environment..."
    "$PYTHON" -m venv "$REPO_DIR/.venv"
    success "Created .venv"
else
    success ".venv already exists"
fi

info "Installing Python dependencies..."
"$REPO_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$REPO_DIR/.venv/bin/pip" install --quiet -r "$REPO_DIR/requirements.txt"
success "Python dependencies installed (PySide6)"

# ── 4. Build Rust OCR binary (optional) ───────────────────────────────────
section "OCR detector (optional)"

if command -v cargo &>/dev/null; then
    info "Rust found — building orbiter OCR binary..."
    if cargo build --release --bin orbiter --manifest-path "$REPO_DIR/Cargo.toml" 2>&1; then
        success "Built target/release/orbiter"
    else
        warn "Rust build failed — the relic reward overlay won't work."
        warn "The rest of the app is unaffected."
    fi
else
    warn "Rust/cargo not found — skipping OCR binary build."
    warn "Install Rust from https://rustup.rs if you want the relic reward overlay."
    warn "After installing Rust, run:  cargo build --release --bin orbiter"
fi

# ── 5. Download Warframe data ─────────────────────────────────────────────
section "Warframe data"

if [[ -f "$REPO_DIR/prices.json" && -f "$REPO_DIR/filtered_items.json" ]]; then
    success "Data files already present — skipping download"
    info "Run ./update.sh any time to refresh prices and item data."
else
    info "Downloading Warframe item and price data (this may take a moment)..."
    if bash "$REPO_DIR/update.sh"; then
        success "Data downloaded"
    else
        warn "Data download failed. You can retry later with:  ./update.sh"
        warn "The app will still launch but item data may be missing."
    fi
fi

# ── 6. Download warframe-api-helper ──────────────────────────────────────
section "warframe-api-helper (inventory)"

if [[ -f "$REPO_DIR/warframe-api-helper" ]]; then
    success "warframe-api-helper already present"
else
    info "Downloading warframe-api-helper from GitHub..."
    if "$REPO_DIR/.venv/bin/python" "$REPO_DIR/download_helper.py"; then
        success "warframe-api-helper downloaded"
    else
        warn "Could not download warframe-api-helper."
        warn "Inventory features won't work until it's installed."
        warn "Run:  python download_helper.py"
    fi
fi

# ── 7. Install icon ─────────────────────────────────────────────────────────
section "Icon"

ICON_SRC="$REPO_DIR/orbiter.svg"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
mkdir -p "$ICON_DIR"

if [[ -f "$ICON_SRC" ]]; then
    cp "$ICON_SRC" "$ICON_DIR/orbiter.svg"
    success "Icon installed to $ICON_DIR/orbiter.svg"
    # Refresh icon cache if gtk-update-icon-cache is available
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
else
    warn "Icon file not found — the app will launch without a custom icon."
fi

# ── 8. Install desktop entry (start menu) ───────────────────────────────────
section "Start menu entry"

DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"

cat > "$DESKTOP_DIR/${DESKTOP_ID}.desktop" << DESKTOP
[Desktop Entry]
Categories=Game;Utility;
Comment=Inventory, relics, rivens, mastery, market — all in one place
Exec=${REPO_DIR}/control-panel.sh
GenericName=Warframe Companion
Icon=orbiter
Keywords=warframe;orbiter;kieda;relics;rivens;inventory;
Name=${APP_NAME}
NoDisplay=false
StartupNotify=true
Terminal=false
Type=Application
DESKTOP

chmod +x "$DESKTOP_DIR/${DESKTOP_ID}.desktop"
success "Desktop entry installed"

# Refresh desktop database so the app appears immediately
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi

# ── 9. Install autostart entries (overlay + watcher run on login) ───────────
section "Autostart entries"

AUTOSTART_DIR="$HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"
_UID="$(id -u)"

# CRITICAL: use env -i to strip any Flatpak/sandbox environment that would
# set the wrong DBUS_SESSION_BUS_ADDRESS and cause focus stealing.
_CLEAN_ENV="env -i HOME=\"\$HOME\" USER=\"\$USER\" LOGNAME=\"\$USER\" SHELL=/bin/bash PATH=\"\$HOME/.local/bin:\$HOME/.cargo/bin:/usr/local/bin:/usr/bin:/bin\" WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/${_UID} DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/${_UID}/bus XDG_DATA_HOME=\"\$HOME/.local/share\" XDG_CACHE_HOME=\"\$HOME/.cache\" XDG_CURRENT_DESKTOP=KDE XDG_SESSION_TYPE=wayland"

cat > "$AUTOSTART_DIR/orbiter-overlay.desktop" << AUTOSTART
[Desktop Entry]
Icon=orbiter
Type=Application
Name=Kieda's Orbiter Overlay
Comment=Pop-up overlay for Warframe relic reward ownership
Exec=/bin/bash -c '${_CLEAN_ENV} setsid ${REPO_DIR}/launch-overlay.sh >> \${HOME}/.local/share/kiedas-orbiter/overlay.log 2>&1 < /dev/null'
X-GNOME-Autostart-enabled=true
NoDisplay=true
Terminal=false
AUTOSTART

cat > "$AUTOSTART_DIR/orbiter-watcher.desktop" << AUTOSTART
[Desktop Entry]
Icon=orbiter
Type=Application
Name=Kieda's Orbiter Warframe Watcher
Comment=Watches for Warframe process and restarts the detector
Exec=/bin/bash -c '${_CLEAN_ENV} setsid ${REPO_DIR}/.venv/bin/python ${REPO_DIR}/warframe-watcher.py >> \${HOME}/.local/share/kiedas-orbiter/watcher.log 2>&1 < /dev/null'
X-GNOME-Autostart-enabled=true
NoDisplay=true
Terminal=false
AUTOSTART

success "Autostart entries installed (overlay + watcher will start on login)"

# ── Compatibility symlink: old wfinfo path → kiedas-orbiter ──────────────
# The detector binary may write to ~/.local/share/wfinfo/ (old name).
# Symlink it so the overlay always finds detections regardless.
OLD_WFINFO_DIR="$HOME/.local/share/wfinfo"
NEW_DATA_DIR="$HOME/.local/share/kiedas-orbiter"
mkdir -p "$OLD_WFINFO_DIR" "$NEW_DATA_DIR"
OLD_STATE="$OLD_WFINFO_DIR/latest-detection.json"
NEW_STATE="$NEW_DATA_DIR/latest-detection.json"
if [[ -f "$OLD_STATE" && ! -L "$OLD_STATE" ]]; then
    # Copy real file content to new location then replace with symlink
    cp "$OLD_STATE" "$NEW_STATE" 2>/dev/null || true
    rm "$OLD_STATE"
fi
if [[ ! -e "$OLD_STATE" ]]; then
    ln -s "$NEW_STATE" "$OLD_STATE"
    success "Created compatibility symlink: wfinfo/ → kiedas-orbiter/"
fi

# ── 10. Make scripts executable ──────────────────────────────────────────────
chmod +x "$REPO_DIR/control-panel.sh" \
         "$REPO_DIR/launch-orbiter.sh" \
         "$REPO_DIR/update.sh" 2>/dev/null || true

# ── Done ──────────────────────────────────────────────────────────────────
echo
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${GREEN}${BOLD}  Installation complete!${RESET}"
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo
echo -e "  ${BOLD}Launch from your start menu:${RESET}  search for \"Kieda's Orbiter\""
echo -e "  ${BOLD}Or run directly:${RESET}              ${REPO_DIR}/control-panel.sh"
echo
echo -e "  On first launch, go to ${BOLD}Status & Tools → File Paths${RESET}"
echo -e "  to verify your EE.log was auto-detected correctly."
echo
