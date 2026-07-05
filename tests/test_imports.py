import pytest
from PySide6.QtWidgets import QApplication


def test_import_tabs():
    """Simple import/instantiation smoke test for tab modules."""
    app = QApplication.instance() or QApplication([])
    import RIVEN_GRADER_TAB as rgt

    tab1 = rgt.RivenGraderTab()

    assert tab1 is not None
    assert hasattr(tab1, '_table')

    import INVENTORY_TAB as invt
    import FOUNDRY_TAB as ft
    import RELIC_PLANNER_TAB as rpt
    import MARKET_TAB as mt
    import MOD_COLLECTION_TAB as mmt
    import SETTINGS_TAB as st

    tab2 = invt.InventoryTab()
    tab3 = ft.FoundryTab()
    tab4 = rpt.RelicPlannerTab()
    tab5 = mt.MarketTab()
    tab6 = mmt.ModCollectionTab()
    tab7 = st.SettingsTab()

    assert tab2._table.rowCount() == len(tab2._owned)
    assert tab3._table.rowCount() == len(tab3._eqmt)
    assert tab4._table.columnCount() == 3
    assert tab5._table.rowCount() > 0
    assert tab6._table.rowCount() > 0

    # Settings tab: all widget keys present, values loadable
    for key, _, typ, *_ in st._FIELDS:
        w = tab7._widgets[key]
        assert w is not None
        _ = w.value() if typ == 'int' else w.text()

    # Verify no None cells in any row across table tabs
    for tab in [tab2, tab5, tab6]:
        for r in range(min(10, tab._table.rowCount())):
            for c in range(tab._table.columnCount()):
                assert tab._table.item(r, c) is not None, \
                    f"{tab.__class__.__name__} row {r} col {c} is None"

    app.quit()
