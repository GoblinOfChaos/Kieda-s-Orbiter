"""
paths.py — centralised path resolution for Kieda's Orbiter.

All EE.log and inventory.json paths go through here.
User overrides are stored in config.json under "ee_log_path" and
"inventory_path".  Auto-detection is used when those are null/blank.

Supported platforms:
  Linux  — Steam (Proton), all common library locations + libraryfolders.vdf
  Windows — Native Warframe install, Steam (Windows), Epic Games Store
  macOS  — Steam (Mac), native Warframe (via Wine/CrossOver if present)
"""

import json
import os
import sys
from pathlib import Path

WFINFO_DIR = Path(__file__).parent
CONFIG_FILE = WFINFO_DIR / "config.json"

# Known Warframe Steam App ID — this never changes
WARFRAME_APPID = "230410"

# ── Platform flags (defined first — used everywhere below) ────────────────
IS_WINDOWS = sys.platform == "win32"
IS_MAC     = sys.platform == "darwin"
IS_LINUX   = sys.platform.startswith("linux")

# ── OS-appropriate data & cache directories ───────────────────────────────
_SANDBOX_INDICATORS = (
    "com.visualstudio.code",
    "com.vscodium",
    "flatpak/exports",
    "io.github.vscodium",
)

def _is_sandbox_path(p: str) -> bool:
    return any(ind in p for ind in _SANDBOX_INDICATORS)


def _get_data_dir() -> Path:
    if IS_WINDOWS:
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
    elif IS_MAC:
        base = Path.home() / "Library" / "Application Support"
    else:
        # Ignore XDG_DATA_HOME if it points to a sandbox environment (VS Code Flatpak etc.)
        xdg = os.environ.get("XDG_DATA_HOME", "")
        if xdg and not _is_sandbox_path(xdg):
            base = Path(xdg)
        else:
            base = Path.home() / ".local/share"
    d = base / "kiedas-orbiter"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get_cache_dir() -> Path:
    if IS_WINDOWS:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    elif IS_MAC:
        base = Path.home() / "Library" / "Caches"
    else:
        xdg = os.environ.get("XDG_CACHE_HOME", "")
        if xdg and not _is_sandbox_path(xdg):
            base = Path(xdg)
        else:
            base = Path.home() / ".cache"
    d = base / "kiedas-orbiter"
    d.mkdir(parents=True, exist_ok=True)
    return d

DATA_DIR  = _get_data_dir()   # persistent app state
CACHE_DIR = _get_cache_dir()  # ephemeral caches (images, etc.)

# ── EE.log relative path inside a Steam Proton prefix (Linux) ────────────
_EE_PROTON_REL = "pfx/drive_c/users/steamuser/AppData/Local/Warframe/EE.log"

# ── EE.log relative path inside a Steam library (Windows/Mac native) ─────
_EE_STEAM_REL  = "steamapps/common/Warframe/EE.log"


def _load_config() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text())
    except Exception:
        return {}


def _save_config(cfg: dict):
    try:
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
    except Exception:
        pass


# ── Platform-specific Steam root locations ────────────────────────────────

def _linux_steam_roots() -> list[Path]:
    roots = [
        Path.home() / ".local/share/Steam",
        Path.home() / ".steam/steam",
        Path.home() / ".steam/root",
        # Flatpak Steam
        Path.home() / ".var/app/com.valvesoftware.Steam/data/Steam",
        # Bazzite / immutable distros with /var/home
        Path("/var/home") / Path.home().name / ".local/share/Steam",
    ]
    return [r for r in roots if r.exists()]


def _windows_steam_roots() -> list[Path]:
    roots = []
    # Standard install locations
    for drive in ["C:", "D:", "E:", "F:"]:
        for sub in [
            "Program Files (x86)/Steam",
            "Program Files/Steam",
            "Steam",
        ]:
            p = Path(f"{drive}/{sub}")
            if p.exists():
                roots.append(p)
    # Registry lookup (best source — won't fail if winreg missing)
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\WOW6432Node\Valve\Steam")
        val, _ = winreg.QueryValueEx(key, "InstallPath")
        p = Path(val)
        if p.exists() and p not in roots:
            roots.append(p)
    except Exception:
        pass
    return roots


def _mac_steam_roots() -> list[Path]:
    return [p for p in [
        Path.home() / "Library/Application Support/Steam",
    ] if p.exists()]


def _get_steam_roots() -> list[Path]:
    if IS_WINDOWS:
        return _windows_steam_roots()
    if IS_MAC:
        return _mac_steam_roots()
    return _linux_steam_roots()


def _extra_steam_libraries(steam_root: Path) -> list[Path]:
    """Parse libraryfolders.vdf to find extra Steam library paths."""
    extras = []
    vdf = steam_root / "steamapps/libraryfolders.vdf"
    if not vdf.exists():
        return extras
    try:
        text = vdf.read_text(errors="ignore")
        for line in text.splitlines():
            line = line.strip()
            if '"path"' in line.lower():
                parts = line.split('"')
                if len(parts) >= 4:
                    p = Path(parts[3])
                    if p.exists():
                        extras.append(p)
    except Exception:
        pass
    return extras


def _find_ee_log_auto() -> Path | None:
    """
    Search all known locations for EE.log, in priority order:

    Linux:   Steam Proton compatdata  →  extra library folders
    Windows: %LOCALAPPDATA%\\Warframe  →  Steam (Windows)  →  Epic Games
    macOS:   ~/Library/Application Support/Steam  →  Wine prefixes
    """
    candidates: list[Path] = []

    # ── Windows ──────────────────────────────────────────────────────────
    if IS_WINDOWS:
        # Native Warframe install (most common on Windows)
        local_app = Path(os.environ.get("LOCALAPPDATA", ""))
        if local_app:
            p = local_app / "Warframe" / "EE.log"
            if p.exists():
                candidates.append(p)

        # Epic Games Store installs
        for drive in ["C:", "D:", "E:", "F:"]:
            for epic_sub in [
                "Program Files/Epic Games/Warframe/EE.log",
                "Program Files (x86)/Epic Games/Warframe/EE.log",
            ]:
                p = Path(f"{drive}/{epic_sub}")
                if p.exists():
                    candidates.append(p)

        # Steam on Windows (native, not Proton)
        for root in _get_steam_roots():
            p = root / _EE_STEAM_REL
            if p.exists():
                candidates.append(p)
            for lib in _extra_steam_libraries(root):
                p = lib / _EE_STEAM_REL
                if p.exists() and p not in candidates:
                    candidates.append(p)

    # ── macOS ─────────────────────────────────────────────────────────────
    elif IS_MAC:
        for root in _get_steam_roots():
            p = root / _EE_STEAM_REL
            if p.exists():
                candidates.append(p)
            for lib in _extra_steam_libraries(root):
                p = lib / _EE_STEAM_REL
                if p.exists() and p not in candidates:
                    candidates.append(p)
        # CrossOver / Wine prefix fallback
        crossover = Path.home() / "Library/Application Support/CrossOver/Bottles"
        if crossover.exists():
            for bottle in crossover.iterdir():
                p = bottle / "drive_c/users/crossover/AppData/Local/Warframe/EE.log"
                if p.exists():
                    candidates.append(p)

    # ── Linux ─────────────────────────────────────────────────────────────
    else:
        for root in _get_steam_roots():
            # Proton path (most common — Steam Play)
            p = root / "steamapps/compatdata" / WARFRAME_APPID / _EE_PROTON_REL
            if p.exists():
                candidates.append(p)
            # Parse extra library folders from VDF
            for lib in _extra_steam_libraries(root):
                p = lib / "steamapps/compatdata" / WARFRAME_APPID / _EE_PROTON_REL
                if p.exists() and p not in candidates:
                    candidates.append(p)

    return candidates[0] if candidates else None


def get_data_dir() -> Path:
    """
    Return the OS-appropriate directory for app data files
    (logs, state, cache).

      Linux:   ~/.local/share/kiedas-orbiter/
      Windows: %APPDATA%\\kiedas-orbiter\\
      macOS:   ~/Library/Application Support/kiedas-orbiter/
    """
    if IS_WINDOWS:
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
    elif IS_MAC:
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    d = base / "kiedas-orbiter"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_ee_log_path() -> Path | None:
    """Return the EE.log path: user override → auto-detect → None."""
    cfg = _load_config()
    override = cfg.get("ee_log_path", "")
    if override and override.strip():
        p = Path(override.strip())
        if p.exists():
            return p
        # Path configured but not found — still return it so caller can warn
        return p
    return _find_ee_log_auto()


def get_inventory_path() -> Path:
    """Return inventory.json path: user override → default."""
    cfg = _load_config()
    override = cfg.get("inventory_path", "")
    if override and override.strip():
        return Path(override.strip())
    return WFINFO_DIR / "inventory.json"


def set_ee_log_path(path_str: str):
    cfg = _load_config()
    cfg["ee_log_path"] = path_str.strip() if path_str.strip() else None
    _save_config(cfg)


def set_inventory_path(path_str: str):
    cfg = _load_config()
    cfg["inventory_path"] = path_str.strip() if path_str.strip() else None
    _save_config(cfg)


def get_screenshot_hotkey() -> str:
    """Return the configured screenshot-trigger hotkey, defaulting to F12.
    Some other software (Steam, GeForce Experience, Xbox Game Bar, VM
    guest tools, etc.) can claim F12 as a global hotkey first, which
    prevents orbiter from registering it - this lets it be changed
    without needing a code change."""
    cfg = _load_config()
    override = cfg.get("screenshot_hotkey", "")
    return override.strip() if override and override.strip() else "F12"


def set_screenshot_hotkey(key_str: str):
    cfg = _load_config()
    cfg["screenshot_hotkey"] = key_str.strip() if key_str.strip() else None
    _save_config(cfg)


def describe_paths() -> dict:
    """Return a dict of path descriptions for display in the UI."""
    ee = get_ee_log_path()
    inv = get_inventory_path()
    cfg = _load_config()
    return {
        "ee_log": {
            "path": str(ee) if ee else "(not found)",
            "exists": ee.exists() if ee else False,
            "is_override": bool(cfg.get("ee_log_path", ""))
        },
        "inventory": {
            "path": str(inv),
            "exists": inv.exists(),
            "is_override": bool(cfg.get("inventory_path", ""))
        },
    }
