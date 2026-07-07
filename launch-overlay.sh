#!/usr/bin/env bash
# launch-overlay.sh — Launch the relic reward overlay on XWayland.
#
# WHY XWayland instead of native Wayland:
#   Warframe runs under gamescope (a nested Wayland compositor). When any
#   new native Wayland surface appears on the host seat, gamescope releases
#   its input grab from the game — stealing focus. Running the overlay on
#   XWayland keeps it inside the same compositor context as the game, so
#   gamescope does not release input when the overlay appears.

set -u
WFINFO_DIR="$(cd "$(dirname "$0")" && pwd)"
QT_LIB_DIR=$(printf "%s:" "$WFINFO_DIR"/.venv/lib*/python*/site-packages/PySide6/Qt/lib | sed 's/:$//')

# ── Find the XWayland DISPLAY ──────────────────────────────────────────────
# Try sockets first, then scan running processes.
XDISPLAY=""
for n in 0 1 2 3 4; do
    if [ -S "/tmp/.X11-unix/X${n}" ]; then
        XDISPLAY=":${n}"
        break
    fi
done

if [ -z "${XDISPLAY}" ]; then
    # Scan process environments for a DISPLAY set by gamescope/Xwayland
    XDISPLAY=$(cat /proc/*/environ 2>/dev/null \
        | tr '\0' '\n' \
        | grep '^DISPLAY=:' \
        | head -1 \
        | cut -d= -f2)
fi

if [ -z "${XDISPLAY}" ]; then
    echo "[launch-overlay] WARNING: no XWayland DISPLAY found, falling back to Wayland" >&2
    QT_PLATFORM=wayland
    XDISPLAY=""
else
    echo "[launch-overlay] Using DISPLAY=${XDISPLAY} (XWayland)" >&2
    QT_PLATFORM=xcb
fi

exec env \
    LD_LIBRARY_PATH="${QT_LIB_DIR}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
    QT_QPA_PLATFORM="${QT_PLATFORM}" \
    DISPLAY="${XDISPLAY}" \
    XDG_DATA_HOME="$HOME/.local/share" \
    XDG_CACHE_HOME="$HOME/.cache" \
    "$WFINFO_DIR/.venv/bin/python" "$WFINFO_DIR/overlay.py" "$@"
