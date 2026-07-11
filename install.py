#!/usr/bin/env python3
"""
install.py — Cross-platform installer for Kieda's Orbiter.

Works on Linux, Windows, and macOS. Run once after cloning:
    python install.py

What it does:
  1. Checks Python version
  2. Checks for Tesseract OCR, offers to install it if missing
  3. Creates a virtual environment and installs dependencies
  4. Downloads pre-built binaries (warframe-api-helper + orbiter)
  5. Downloads the latest Warframe item/price data
  6. Creates a start menu / desktop entry so the app is launchable

Note: The Rust build step has been replaced with downloading pre-built binaries
      from GitHub releases. This removes the need for users to install Rust.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

WFINFO_DIR = Path(__file__).parent

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
IS_MAC = sys.platform == "darwin"

# ── Colours ───────────────────────────────────────────────────────────────
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
GREEN = "\033[0;32m"
CYAN = "\033[0;36m"
BOLD = "\033[1m"
RESET = "\033[0m"

if IS_WINDOWS:
    # Windows cmd doesn't support ANSI by default; disable colours
    RED = YELLOW = GREEN = CYAN = BOLD = RESET = ""

def info(msg):    print(f"{CYAN}▶{RESET}  {msg}")
def success(msg): print(f"{GREEN}✓{RESET}  {msg}")
def warn(msg):    print(f"{YELLOW}!{RESET}  {msg}")
def fail(msg):    print(f"{RED}✗{RESET}  {msg}"); sys.exit(1)
def section(msg): print(f"\n{BOLD}── {msg} ──────────────────────────────────{RESET}")


# ── 1. Check Python version ───────────────────────────────────────────────
section("Python")
if sys.version_info < (3, 11):
    fail(f"Python 3.11+ required. You have {sys.version}. "
         "Install from https://python.org")
success(f"Python {sys.version.split()[0]}")


# ── 2. Check Tesseract ─────────────────────────────────────────────────────
section("Tesseract OCR")


def _prompt_yes_no(question: str, default_yes: bool = True) -> bool:
    if not sys.stdin.isatty():
        return False
    suffix = "[Y/n]" if default_yes else "[y/N]"
    try:
        answer = input(f"  {question} {suffix} ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default_yes
    return answer.startswith("y")


def _try_run(cmd: list[str]) -> bool:
    info(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd)
        return result.returncode == 0
    except FileNotFoundError:
        return False


tesseract_missing = False
if shutil.which("tesseract"):
    result = subprocess.run(["tesseract", "--version"], capture_output=True, text=True)
    success(f"Tesseract found: {result.stdout.splitlines()[0]}")
else:
    tesseract_missing = True
    warn("Tesseract not found — relic reward OCR overlay won't work without it.")

    install_cmd = None
    needs_reboot = False
    if IS_LINUX:
        is_atomic = shutil.which("rpm-ostree") is not None
        has_brew = shutil.which("brew") is not None
        if has_brew:
            install_cmd = ["brew", "install", "tesseract"]
        elif is_atomic:
            warn("This is an atomic/immutable distro (Fedora Silverblue, Bazzite, etc).")
            warn("Plain 'dnf install' won't work on the host.")
            install_cmd = ["sudo", "rpm-ostree", "install", "-y", "tesseract"]
            needs_reboot = True
        elif shutil.which("apt-get"):
            install_cmd = ["sudo", "apt-get", "install", "-y", "tesseract-ocr"]
        elif shutil.which("dnf"):
            install_cmd = ["sudo", "dnf", "install", "-y", "tesseract"]
        elif shutil.which("pacman"):
            install_cmd = ["sudo", "pacman", "-S", "--noconfirm", "tesseract"]
    elif IS_WINDOWS:
        if shutil.which("winget"):
            install_cmd = ["winget", "install", "--id", "UB-Mannheim.TesseractOCR", "-e",
                            "--accept-package-agreements", "--accept-source-agreements"]
        else:
            warn("winget not found. Download manually from:")
            warn("  https://github.com/UB-Mannheim/tesseract/wiki")
    elif IS_MAC:
        if shutil.which("brew"):
            install_cmd = ["brew", "install", "tesseract"]
        else:
            warn("Homebrew not found. Install it from https://brew.sh, then:")
            warn("  brew install tesseract")

    if install_cmd:
        warn(f"Install command: {' '.join(install_cmd)}")
        if needs_reboot:
            warn("Note: this requires a reboot before Tesseract becomes usable.")
        if _prompt_yes_no("Install it now?"):
            if _try_run(install_cmd):
                if shutil.which("tesseract"):
                    tesseract_missing = False
                    success("Tesseract installed successfully.")
                elif needs_reboot:
                    warn("Layered — reboot, then re-run this installer to confirm.")
                else:
                    warn("Install command finished but 'tesseract' still isn't on PATH.")
            else:
                warn("Install command failed. Run it manually, or check the error above.")
        else:
            warn("Skipped. Run the command above manually any time before playing.")


# ── 3. Virtual environment ────────────────────────────────────────────────
section("Virtual environment")

VENV = WFINFO_DIR / ".venv"
if IS_WINDOWS:
    VENV_PYTHON = VENV / "Scripts" / "python.exe"
    VENV_PIP = VENV / "Scripts" / "pip.exe"
else:
    VENV_PYTHON = VENV / "bin" / "python"
    VENV_PIP = VENV / "bin" / "pip"

if not VENV.exists():
    info("Creating virtual environment...")
    subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
    success("Created .venv")
else:
    success(".venv already exists")

info("Installing Python dependencies...")
subprocess.run([str(VENV_PIP), "install", "--quiet", "--upgrade", "pip"], check=True)
subprocess.run([str(VENV_PIP), "install", "--quiet", "-r", str(WFINFO_DIR / "requirements.txt")], check=True)
success("Python dependencies installed (PySide6, psutil)")


# ── 4. Download pre-built binaries (replaces Rust build) ─────────────────
section("Pre-built binaries")

info("Downloading warframe-api-helper and orbiter from GitHub releases...")

sys.path.insert(0, str(WFINFO_DIR))
try:
    from download_helper import download_helper
    result = download_helper()
    
    if result["api_helper"] and result["orbiter"]:
        success("Both binaries downloaded successfully!")
    elif result["api_helper"]:
        warn("warframe-api-helper downloaded, but orbiter is missing.")
        warn("Relic reward OCR overlay won't work until orbiter is installed.")
    else:
        fail("Failed to download required binaries. Inventory features won't work.")
except ImportError as e:
    fail(f"Could not import download_helper: {e}")
    fail("Make sure you're running this from the project directory.")
except Exception as e:
    warn(f"Binary download encountered an issue: {e}")
    warn("Inventory features won't work until binaries are installed correctly.")


# ── 5. Download Warframe data ─────────────────────────────────────────────
section("Warframe data")
prices = WFINFO_DIR / "prices.json"
items = WFINFO_DIR / "filtered_items.json"

if prices.exists() and items.exists():
    success("Data files already present")
    info("Run 'python update.py' any time to refresh prices and item data.")
else:
    info("Downloading Warframe data (this may take a moment)...")
    # Use update_manager's quick_update, which falls back to local WFCD
    # synthesis if the direct download fails — more resilient than a single
    # unretried download attempt.
    result = subprocess.run(
        [str(VENV_PYTHON), "-c",
         "from update_manager import quick_update; import sys; "
         "r = quick_update(); "
         "sys.exit(0 if all(v in ('updated', 'synthesized', 'current') for v in r.values()) else 1)"],
        cwd=str(WFINFO_DIR),
    )
    if result.returncode == 0:
        success("Warframe data downloaded")
    else:
        warn("Data download failed. The app will retry automatically on first launch.")


# ── 6. Install icon + start menu entry ───────────────────────────────────
section("Start menu / desktop entry")

if IS_LINUX:
    uid_val = os.getuid()
    icon_dir = Path.home() / ".local/share/icons/hicolor/scalable/apps"
    icon_dir.mkdir(parents=True, exist_ok=True)
    icon_src = WFINFO_DIR / "orbiter.svg"
    if icon_src.exists():
        shutil.copy(icon_src, icon_dir / "orbiter.svg")
        success(f"Icon installed")

    autostart_dir = Path.home() / ".config/autostart"
    apps_dir = Path.home() / ".local/share/applications"
    autostart_dir.mkdir(parents=True, exist_ok=True)
    apps_dir.mkdir(parents=True, exist_ok=True)

    clean_env = (
        f'env -i HOME="$HOME" USER="$USER" LOGNAME="$USER" SHELL=/bin/bash '
        f'PATH="$HOME/.local/bin:$HOME/.cargo/bin:/usr/local/bin:/usr/bin:/bin" '
        f'WAYLAND_DISPLAY=wayland-0 '
        f'XDG_RUNTIME_DIR=/run/user/{uid_val} '
        f'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid_val}/bus '
        f'XDG_DATA_HOME="$HOME/.local/share" XDG_CACHE_HOME="$HOME/.cache" '
        f'XDG_CURRENT_DESKTOP=KDE XDG_SESSION_TYPE=wayland'
    )

    # Main app .desktop
    (apps_dir / "kiedas-orbiter.desktop").write_text(f"""[Desktop Entry]
Categories=Game;Utility;
Comment=Inventory, relics, rivens, mastery, market — all in one place
Exec={WFINFO_DIR}/launcher.py app
GenericName=Warframe Companion
Icon=orbiter
Keywords=warframe;orbiter;kieda;relics;rivens;inventory;
Name=Kieda's Orbiter
NoDisplay=false
StartupNotify=true
Terminal=false
Type=Application
""")

    # Overlay autostart
    (autostart_dir / "orbiter-overlay.desktop").write_text(f"""[Desktop Entry]
Icon=orbiter
Type=Application
Name=Kieda's Orbiter Overlay
Comment=Pop-up overlay for Warframe relic reward ownership
Exec=/bin/bash -c '{clean_env} setsid {VENV_PYTHON} {WFINFO_DIR}/launcher.py overlay >> {Path.home()}/.local/share/kiedas-orbiter/overlay.log 2>&1 < /dev/null'
X-GNOME-Autostart-enabled=true
NoDisplay=true
Terminal=false
""")

    # Watcher autostart
    (autostart_dir / "orbiter-watcher.desktop").write_text(f"""[Desktop Entry]
Icon=orbiter
Type=Application
Name=Kieda's Orbiter Warframe Watcher
Comment=Watches for Warframe process and restarts the detector
Exec=/bin/bash -c '{clean_env} setsid {VENV_PYTHON} {WFINFO_DIR}/launcher.py watcher >> {Path.home()}/.local/share/kiedas-orbiter/watcher.log 2>&1 < /dev/null'
X-GNOME-Autostart-enabled=true
NoDisplay=true
Terminal=false
""")

    # Symlink: ~/.local/share/wfinfo -> kiedas-orbiter (compatibility)
    wfinfo_old = Path.home() / ".local/share/wfinfo"
    wfinfo_new = Path.home() / ".local/share/kiedas-orbiter"
    wfinfo_new.mkdir(parents=True, exist_ok=True)
    if not wfinfo_old.exists():
        wfinfo_old.symlink_to(wfinfo_new)

    subprocess.run(["update-desktop-database", str(apps_dir)], capture_output=True)
    success("Desktop entry + autostart files installed")

elif IS_WINDOWS:
    # Create a Start Menu shortcut via PowerShell
    start_menu = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs"
    start_menu.mkdir(parents=True, exist_ok=True)
    lnk = start_menu / "Kieda's Orbiter.lnk"
    launcher = WFINFO_DIR / "launcher.py"
    ps_script = f"""
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{lnk}')
$Shortcut.TargetPath = '{VENV_PYTHON}'
$Shortcut.Arguments = '"{launcher}" app'
$Shortcut.WorkingDirectory = '{WFINFO_DIR}'
$Shortcut.Description = "Kieda's Orbiter — Warframe Companion"
$Shortcut.Save()
"""
    result = subprocess.run(["powershell", "-Command", ps_script], capture_output=True)
    if result.returncode == 0:
        success(f"Start Menu shortcut created")
    else:
        warn("Could not create Start Menu shortcut automatically.")
        warn(f"To launch manually: python {launcher} app")

elif IS_MAC:
    warn("macOS: no automatic desktop entry — launch with: python launcher.py app")


# ── Done ──────────────────────────────────────────────────────────────────
print()
print(f"{GREEN}{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
print(f"{GREEN}{BOLD}  Installation complete!{RESET}")
print(f"{GREEN}{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
print()
if IS_LINUX:
    print(f"  {BOLD}Launch from start menu:{RESET}  search for \"Kieda's Orbiter\"")
    print(f"  {BOLD}Or run directly:{RESET}        python {WFINFO_DIR}/launcher.py app")
elif IS_WINDOWS:
    print(f"  {BOLD}Launch from Start Menu:{RESET}  search for \"Kieda's Orbiter\"")
    print(f"  {BOLD}Or run directly:{RESET}        python launcher.py app")
print()
print(f"  On first launch, go to {BOLD}Status & Tools → File Paths{RESET}")
print(f"  to verify your EE.log was auto-detected correctly.")
print()
if tesseract_missing:
    print(f"{YELLOW}{BOLD}⚠ IMPORTANT: Tesseract OCR is not installed.{RESET}")
    print(f"{YELLOW}  The relic reward overlay will NOT work until you install it —")
    print(f"  see the 'Tesseract OCR' section above for the exact command.{RESET}")
    print()
