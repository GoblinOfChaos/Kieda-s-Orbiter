#!/bin/bash
set -u
WFINFO_DIR="$HOME/wfinfo-ng"
# collect PySide6 Qt lib dirs and join with ':' so LD_LIBRARY_PATH is valid
QT_LIB_DIR=$(printf "%s:" "$WFINFO_DIR"/.venv/lib*/python*/site-packages/PySide6/Qt/lib | sed 's/:$//')

# Auto-detect the appropriate Qt platform plugin
if [ -n "${WAYLAND_DISPLAY-}" ]; then
    QT_PLATFORM=wayland
elif [ -n "${DISPLAY-}" ]; then
    QT_PLATFORM=xcb
else
    QT_PLATFORM=offscreen
fi

exec env \
    LD_LIBRARY_PATH="${QT_LIB_DIR}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
    QT_QPA_PLATFORM="$QT_PLATFORM" \
    XDG_DATA_HOME="$HOME/.local/share" \
    XDG_CACHE_HOME="$HOME/.cache" \
    "$WFINFO_DIR/.venv/bin/python" "$WFINFO_DIR/missing-parts.py"
