#!/usr/bin/env python3
"""Headless runner to instantiate tabs and print row counts."""
from PySide6.QtWidgets import QApplication
import importlib.util
from pathlib import Path


def _load_module_from_path(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    app = QApplication([])
    try:
        base = Path(__file__).resolve().parent.parent
        rg_mod = _load_module_from_path(base / 'RIVEN_GRADER_TAB.py', 'RIVEN_GRADER_TAB')
        RivenGraderTab = getattr(rg_mod, 'RivenGraderTab')
        rg = RivenGraderTab()
        print('RivenGrader rows:', rg._table.rowCount())

        mm_path = base / 'MOD_COLLECTION_TAB.py'
        if mm_path.exists():
            mm_mod = _load_module_from_path(mm_path, 'MOD_COLLECTION_TAB')
            ModCollectionTab = getattr(mm_mod, 'ModCollectionTab')
            mm = ModCollectionTab()
            print('ModCollection rows:', mm._table.rowCount())
        else:
            print('Mod Collection tab not present; skipped')
    finally:
        app.quit()

if __name__ == '__main__':
    main()
