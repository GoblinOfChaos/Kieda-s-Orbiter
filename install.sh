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

# ── 6. Install icon ───────────────────────────────────────────────────────
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

# ── 7. Install desktop entry (start menu) ────────────────────────────────
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

# ── 8. Make scripts executable ────────────────────────────────────────────
chmod +x "$REPO_DIR/control-panel.sh" \
         "$REPO_DIR/launch-orbiter.sh" \
         "$REPO_DIR/update.sh" \
         "$REPO_DIR/missing-parts.py" 2>/dev/null || true

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
