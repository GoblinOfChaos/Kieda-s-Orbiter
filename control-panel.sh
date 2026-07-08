#!/bin/bash
# Thin wrapper — delegates to launcher.py which works on Linux, Windows, macOS.
WFINFO_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$WFINFO_DIR/.venv/bin/python" "$WFINFO_DIR/launcher.py" app "$@"
