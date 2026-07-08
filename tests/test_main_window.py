import importlib.util
import os
import sys
from pathlib import Path

import pytest
from PyQt6.QtCore import QProcess
from PyQt6.QtWidgets import QApplication, QListWidget, QStackedWidget
from unittest.mock import MagicMock, patch


def _load_main_window_module():
    project_root = Path(__file__).resolve().parent.parent
    src_dir = project_root / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    module_path = src_dir / "gui" / "pyqt6" / "main_window.py"
    spec = importlib.util.spec_from_file_location("main_window_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_window_can_be_instantiated(qapp: QApplication) -> None:
    with patch("gui.pyqt6.cli_bridge.QProcess") as mock_qprocess:
        mock_qprocess.ProcessState.NotRunning = QProcess.ProcessState.NotRunning
        mock_qprocess.ProcessError.Crashed = QProcess.ProcessError.Crashed
        mock_instance = MagicMock()
        mock_instance.state.return_value = QProcess.ProcessState.NotRunning
        mock_instance.waitForStarted.return_value = True
        mock_qprocess.return_value = mock_instance

        module = _load_main_window_module()
        module.MaaEndControlPage._sync_execute = lambda self, command, timeout_ms=5000: {"status": "success"}
        window = module.MainWindow()
        assert window is not None
        assert window.windowTitle() == "Istina Endfield Assistant"


def test_main_window_bridge_returns_cli_bridge(qapp: QApplication) -> None:
    with patch("gui.pyqt6.cli_bridge.QProcess") as mock_qprocess:
        mock_qprocess.ProcessState.NotRunning = QProcess.ProcessState.NotRunning
        mock_qprocess.ProcessError.Crashed = QProcess.ProcessError.Crashed
        mock_instance = MagicMock()
        mock_instance.state.return_value = QProcess.ProcessState.NotRunning
        mock_instance.waitForStarted.return_value = True
        mock_qprocess.return_value = mock_instance

        module = _load_main_window_module()
        module.MaaEndControlPage._sync_execute = lambda self, command, timeout_ms=5000: {"status": "success"}
        window = module.MainWindow()
        bridge = window.bridge()
        assert bridge is not None
        assert type(bridge).__name__ == "CLIBridge"


def test_main_window_uses_left_navigation_and_correct_page_mapping(qapp: QApplication) -> None:
    with patch("gui.pyqt6.cli_bridge.QProcess") as mock_qprocess:
        mock_qprocess.ProcessState.NotRunning = QProcess.ProcessState.NotRunning
        mock_qprocess.ProcessError.Crashed = QProcess.ProcessError.Crashed
        mock_instance = MagicMock()
        mock_instance.state.return_value = QProcess.ProcessState.NotRunning
        mock_instance.waitForStarted.return_value = True
        mock_qprocess.return_value = mock_instance

        module = _load_main_window_module()
        module.MaaEndControlPage._sync_execute = lambda self, command, timeout_ms=5000: {"status": "success"}
        window = module.MainWindow()

        nav = window.findChild(QListWidget, "mainNavigation")
        stack = window.findChild(QStackedWidget)

        assert nav is not None
        assert stack is not None
        assert [nav.item(i).text() for i in range(nav.count())] == [
            "PRTS 全智能",
            "标准推理",
            "设备",
            "设置",
            "日志",
        ]
        assert stack.count() == 5
        assert type(stack.widget(0)).__name__ == "PrtsFullIntelligencePage"
        assert all(nav.item(i).text() != "MaaEnd" for i in range(nav.count()))
        labels = [w.text() for w in stack.widget(0).findChildren(module.QLabel)]
        assert "PRTS 全智能" in labels
        assert "自动化分析与智能决策控制台。" in labels
