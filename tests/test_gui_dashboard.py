"""Tests for gui.pyqt6.dashboard widgets and registry."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PyQt6.QtCore import QEvent, QMimeData, QPoint, QPointF, Qt
from PyQt6.QtGui import QDrag, QEnterEvent, QMouseEvent
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox

from gui.pyqt6.cli_bridge import CLIBridge
from gui.pyqt6.dashboard.widget_registry import WidgetRegistry, get_widget_registry
from gui.pyqt6.dashboard.widget_base import DashboardWidget
from gui.pyqt6.dashboard.widgets.device_status_widget import DeviceStatusWidget
from gui.pyqt6.dashboard.widgets.queue_progress_widget import QueueProgressWidget
from gui.pyqt6.dashboard.widgets.llm_status_widget import LLMStatusWidget
from gui.pyqt6.dashboard.dashboard_page import DashboardPage
from gui.pyqt6.dashboard.widget_market_dialog import WidgetMarketDialog
from gui.pyqt6.i18n import get_locale_manager

locale = get_locale_manager()


@pytest.fixture(autouse=True)
def _suppress_message_boxes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **kw: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **kw: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **kw: None)


def _make_bridge(monkeypatch: pytest.MonkeyPatch) -> CLIBridge:
    bridge = CLIBridge()
    monkeypatch.setattr(bridge, "execute", lambda command, params=None: None)
    return bridge


class TestWidgetRegistry:
    def test_register_and_get_available_widgets(self) -> None:
        registry = WidgetRegistry()
        registry.register("test", "Test Widget", "A test widget", object)
        widgets = registry.get_available_widgets()
        assert "test" in widgets
        assert widgets["test"]["name"] == "Test Widget"

    def test_get_widget_returns_none_for_missing(self) -> None:
        registry = WidgetRegistry()
        assert registry.get_widget("missing") is None

    def test_is_registered(self) -> None:
        registry = WidgetRegistry()
        registry.register("a", "A", "desc", object)
        assert registry.is_registered("a") is True
        assert registry.is_registered("b") is False

    def test_global_registry_has_builtins(self) -> None:
        registry = get_widget_registry()
        assert registry.is_registered("device")
        assert registry.is_registered("queue")
        assert registry.is_registered("llm")


class TestDashboardWidgetBase:
    def test_content_widget_returns_container(self, qapp: QApplication) -> None:
        widget = DashboardWidget("Test")
        content = widget.content_widget()
        assert content is widget._content

    def test_update_content_replaces_children(self, qapp: QApplication) -> None:
        widget = DashboardWidget("Test")
        from PyQt6.QtWidgets import QLabel
        old = widget.content_widget()
        assert old.layout().count() == 0

        label = QLabel("hello")
        widget.update_content(label)
        assert old.layout().count() == 1

    def test_enter_leave_event_changes_style(self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
        widget = DashboardWidget("Test")
        original = widget.styleSheet()
        monkeypatch.setattr("PyQt6.QtWidgets.QFrame.enterEvent", lambda self, event: None)
        monkeypatch.setattr("PyQt6.QtWidgets.QFrame.leaveEvent", lambda self, event: None)
        widget.enterEvent(QEvent(QEvent.Type.Enter))
        assert widget.styleSheet() != original
        widget.leaveEvent(QEvent(QEvent.Type.Leave))
        assert widget.styleSheet() == original

    def test_set_selected_true_applies_style(self, qapp: QApplication) -> None:
        widget = DashboardWidget("Test")
        widget.set_selected(True)
        style = widget.styleSheet()
        assert len(style) > 0

    def test_set_selected_false_restores_style(self, qapp: QApplication) -> None:
        widget = DashboardWidget("Test")
        widget.set_selected(True)
        widget.set_selected(False)
        style = widget.styleSheet()
        assert len(style) > 0

    def test_fade_in_does_not_crash(self, qapp: QApplication) -> None:
        widget = DashboardWidget("Test")
        widget.fade_in(200)  # 不报错即为通过

    def test_start_stop_auto_refresh(self, qapp: QApplication) -> None:
        widget = DashboardWidget("Test")
        widget.start_auto_refresh()
        assert widget._refresh_timer.isActive()
        widget.stop_auto_refresh()
        assert not widget._refresh_timer.isActive()

    def test_mouse_press_and_move_drag(self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
        widget = DashboardWidget("Test")
        drag_called = False

        class FakeDrag:
            def __init__(self, *args, **kwargs):
                pass
            def setPixmap(self, *args, **kwargs):
                pass
            def setHotSpot(self, *args, **kwargs):
                pass
            def exec(self):
                nonlocal drag_called
                drag_called = True
            def mimeData(self):
                return FakeMimeData()

        class FakeMimeData:
            def setData(self, *args, **kwargs):
                pass

        monkeypatch.setattr("gui.pyqt6.dashboard.widget_base.QDrag", FakeDrag)

        from PyQt6.QtCore import QPoint
        from PyQt6.QtGui import QMouseEvent
        widget._drag_start_pos = QPoint(0, 0)
        widget.mouseMoveEvent(QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(20, 20),
            QPointF(20, 20),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        ))
        assert drag_called is True


class TestDeviceQueueLLMStatusWidgets:
    def test_device_status_widget_empty(self, qapp: QApplication) -> None:
        widget = DeviceStatusWidget("Device", None)
        widget.play_success = lambda: None
        widget.update_data([])
        assert widget._status_label.text() == locale.tr("offline", "Offline")
        assert widget._serial_label.text() == "-"

    def test_device_status_widget_with_device(self, qapp: QApplication) -> None:
        widget = DeviceStatusWidget("Device", None)
        widget.play_success = lambda: None
        widget.update_data([{"serial": "ABC123"}])
        assert widget._status_label.text() == locale.tr("online", "Online")
        assert widget._serial_label.text() == "ABC123"

    def test_queue_progress_widget_running(self, qapp: QApplication) -> None:
        widget = QueueProgressWidget("Queue", None)
        widget.update_data({"status": "running"})
        assert widget._status_label.text() == locale.tr("maaend_running", "Running")

    def test_queue_progress_widget_completed(self, qapp: QApplication) -> None:
        widget = QueueProgressWidget("Queue", None)
        widget.play_success = lambda: None
        widget.update_data({"status": "success"})
        assert widget._status_label.text() == locale.tr("execution_completed", "Completed")

    def test_llm_status_widget_enabled(self, qapp: QApplication) -> None:
        widget = LLMStatusWidget("LLM", None)
        widget.play_success = lambda: None
        widget.update_data({"enabled": True})
        assert widget._status_label.text() == locale.tr("online", "Online")

    def test_llm_status_widget_disabled(self, qapp: QApplication) -> None:
        widget = LLMStatusWidget("LLM", None)
        widget.update_data({"enabled": False})
        assert widget._status_label.text() == locale.tr("disabled_status", "Disabled")


class TestDashboardPage:
    def test_resolve_config_path_returns_path(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(
            "core.foundation.paths.get_project_root",
            lambda: tmp_path,
        )
        page = DashboardPage.__new__(DashboardPage)
        path = page._resolve_config_path()
        assert path == tmp_path / "config" / "dashboard_layout.json"

    def test_setup_ui_creates_grid(self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(
            "core.foundation.paths.get_project_root",
            lambda: tmp_path,
        )
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
        (tmp_path / "config" / "dashboard_layout.json").write_text("{}", encoding="utf-8")
        bridge = _make_bridge(monkeypatch)
        page = DashboardPage(bridge)
        page._poll_timer.stop()
        assert page._grid is not None

    def test_create_widget_known_id(self, qapp: QApplication) -> None:
        page = DashboardPage.__new__(DashboardPage)
        page._bridge = None
        widget = page._create_widget("device", "Device Status")
        assert widget is not None
        assert isinstance(widget, DeviceStatusWidget)

    def test_create_widget_unknown_id(self, qapp: QApplication) -> None:
        page = DashboardPage.__new__(DashboardPage)
        page._bridge = None
        assert page._create_widget("unknown", "Unknown") is None

    def test_load_layout_adds_defaults_when_missing(
        self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(
            "core.foundation.paths.get_project_root",
            lambda: tmp_path,
        )
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
        bridge = _make_bridge(monkeypatch)
        page = DashboardPage(bridge)
        page._poll_timer.stop()
        assert len(page._grid_widgets) >= 1

    def test_drag_events_accept_widget_mime(
        self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(
            "core.foundation.paths.get_project_root",
            lambda: tmp_path,
        )
        (tmp_path / "config").mkdir(parents=True, exist_ok=True)
        (tmp_path / "config" / "dashboard_layout.json").write_text("{}", encoding="utf-8")
        bridge = _make_bridge(monkeypatch)
        page = DashboardPage(bridge)
        page._poll_timer.stop()

        mime = QMimeData()
        mime.setData("application/x-dashboard-widget", b"device")
        event = type("Event", (), {
            "mimeData": lambda self: mime,
            "accept": lambda self: None,
            "ignore": lambda self: None,
            "pos": lambda self: QPoint(0, 0),
        })()
        page.dragEnterEvent(event)
        page.dragMoveEvent(event)
        page.dropEvent(event)


class TestWidgetMarketDialog:
    def test_setup_ui_creates_list(self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
        bridge = _make_bridge(monkeypatch)
        dialog = WidgetMarketDialog(bridge)
        assert dialog._widget_list is not None
        assert dialog._widget_list.count() > 0

    def test_selection_changed_updates_id(self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
        bridge = _make_bridge(monkeypatch)
        dialog = WidgetMarketDialog(bridge)
        dialog._widget_list.setCurrentRow(0)
        dialog._on_selection_changed()
        assert dialog._selected_widget_id is not None

    def test_selected_widget_id_returns_none_when_no_selection(self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
        bridge = _make_bridge(monkeypatch)
        dialog = WidgetMarketDialog(bridge)
        assert dialog.selected_widget_id() is None
