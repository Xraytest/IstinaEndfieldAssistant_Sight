"""Quick reproduction for CreditShopping option display."""
from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from gui.pyqt6.cli_bridge import CLIBridge
from gui.pyqt6.pages.maaend_control_page import MaaEndControlPage


def test_credit_shopping_options_display():
    app = QApplication.instance() or QApplication([])

    import gui.pyqt6.pages.maaend_control_page as _mod
    _mod.MaaEndControlPage._delayed_init = lambda self: None

    bridge = CLIBridge()
    bridge._start_interactive_process = lambda: None

    page = MaaEndControlPage(bridge=bridge, parent=None)
    page.show()

    from PyQt6.QtCore import QCoreApplication
    QCoreApplication.processEvents()

    page._tasks_cache = {
        "CreditShoppingN2": {
            "name": "CreditShoppingN2",
            "option": [
                "CreditShoppingReserve",
                "CreditShoppingClueSend",
                "CreditShoppingClueStockLimit",
                "CreditShoppingPriority1",
                "CreditShoppingPriority2",
                "CreditShoppingPriority3",
                "CreditShoppingForce",
                "CreditShoppingKeepShelfRecord",
            ],
            "_option_defs": {},
        }
    }

    opt_path = Path("assets/tasks/CreditShopping.json")
    data = json.loads(opt_path.read_text(encoding="utf-8"))
    page._task_option_defs = data.get("option", {})

    page._selected_task = "CreditShoppingN2"
    page._build_option_editor()

    # Process pending layout updates
    QCoreApplication.processEvents()

    widget_count = len(page._option_widgets)
    tree_count = len(page._option_tree)
    print(f"Option widgets: {widget_count}")
    print(f"Option tree nodes: {tree_count}")

    # 顶层 8 个 + 子选项 9 个 = 17
    assert widget_count == 17, f"Expected 17 widgets, got {widget_count}"
    assert tree_count == 17, f"Expected 17 tree nodes, got {tree_count}"

    for name, node in page._option_tree.items():
        sub_visible = node["sub_container"].isVisible()
        children = list(node["children"].keys())
        print(f"{name}: sub_visible={sub_visible}, children={children}")

    # 只断言有子选项且应该显示的节点
    assert page._option_tree["CreditShoppingPriority1"]["sub_container"].isVisible()
    assert len(page._option_tree["CreditShoppingPriority1"]["children"]) > 0
    assert page._option_tree["CreditShoppingPriority2"]["sub_container"].isVisible()
    assert len(page._option_tree["CreditShoppingPriority2"]["children"]) > 0
    # Priority3 default is No -> no sub-options visible
    assert not page._option_tree["CreditShoppingPriority3"]["sub_container"].isVisible()
