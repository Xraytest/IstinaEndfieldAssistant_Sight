"""Tests for dashboard widget registry, base widget, page, and widget market."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QMouseEvent, QShowEvent
from PyQt6.QtTest import QTest

from gui.pyqt6.dashboard.widget_registry import WidgetRegistry, get_widget_registry
from gui.pyqt6.dashboard.widget_base import DashboardWidget
from gui.pyqt6.dashboard.dashboard_page import DashboardPage
from gui.pyqt6.dashboard.widget_market_dialog import WidgetMarketDialog


class TestWidgetRegistry:
    """Test WidgetRegistry class."""

    def test_register_and_get(self) -> None:
        registry = WidgetRegistry()
        registry.register("w1", "Name 1", "Desc 1", dict)
        registry.register("w2", "Name 2", "Desc 2", list)
        assert registry.is_registered("w1")
        assert not registry.is_registered("w3")
        info = registry.get_widget("w1")
        assert info["name"] == "Name 1"
        assert info["class"] is dict
        assert info["description"] == "Desc 1"
        assert len(registry.get_available_widgets()) == 2

    def test_get_widget_missing_returns_none(self) -> None:
        registry = WidgetRegistry()
        assert registry.get_widget("missing") is None

    def test_global_registry_singleton(self) -> None:
        r1 = get_widget_registry()
        r2 = get_widget_registry()
        assert r1 is r2


class TestDashboardWidgetBase:
    """Test DashboardWidget base class behavior."""

    def test_content_widget_returns_internal_widget(self, qapp: QApplication) -> None:
        widget = DashboardWidget("Test", "id1")
        content = widget.content_widget()
        assert content is widget._content

    def test_update_content_replaces_children(self, qapp: QApplication) -> None:
        from PyQt6.QtWidgets import QLabel
        widget = DashboardWidget("Test", "id1")
        lbl = QLabel("hello")
        widget.update_content(lbl)
        assert widget._content_layout.count() == 1
        assert widget._content_layout.itemAt(0).widget() is lbl

    def test_set_selected_true_and_false(self, qapp: QApplication) -> None:
        widget = DashboardWidget("Test", "id1")
        widget.set_selected(True)
        widget.set_selected(False)
        assert widget.styleSheet() != ""

    def test_start_stop_auto_refresh(self, qapp: QApplication) -> None:
        widget = DashboardWidget("Test", "id1")
        widget.start_auto_refresh()
        assert widget._refresh_timer.isActive()
        widget.stop_auto_refresh()
        assert not widget._refresh_timer.isActive()

    def test_enter_leave_event_changes_style(self, qapp: QApplication) -> None:
        widget = DashboardWidget("Test", "id1")
        widget.enterEvent(None)
        widget.leaveEvent(None)
        # Should not crash

    def test_fade_in_does_not_crash(self, qapp: QApplication) -> None:
        widget = DashboardWidget("Test", "id1")
        widget.fade_in(200)

    def test_mouse_press_and_move_drag_start(self, qapp: QApplication) -> None:
        from PyQt6.QtCore import QPointF
        widget = DashboardWidget("Test", "id1")
        event = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(5, 5),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        widget.mousePressEvent(event)
        widget.mouseMoveEvent(event)


class TestDashboardWidgetsUpdateData:
    """Test DeviceStatusWidget, QueueProgressWidget, LLMStatusWidget update_data."""

    def test_device_status_widget_update_data(self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
        from gui.pyqt6.dashboard.widgets.device_status_widget import DeviceStatusWidget
        monkeypatch.setattr(DeviceStatusWidget, "play_success", lambda self: None, raising=False)
        w = DeviceStatusWidget("Device", bridge=None)
        assert w._status_label.text() != ""
        w.update_data([])
        assert w._status_label.text() != ""
        w.update_data([{"serial": "abc123", "status": "device"}])
        assert "abc123" in w._serial_label.text()

    def test_queue_progress_widget_update_data(self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
        from gui.pyqt6.dashboard.widgets.queue_progress_widget import QueueProgressWidget
        monkeypatch.setattr(QueueProgressWidget, "play_success", lambda self: None, raising=False)
        w = QueueProgressWidget("Queue", bridge=None)
        w.update_data({"status": "running"})
        assert w._status_label.text() != ""
        w.update_data({"status": "success"})
        assert w._status_label.text() != ""
        w.update_data({"status": "failed"})
        assert w._status_label.text() != ""

    def test_llm_status_widget_update_data(self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
        from gui.pyqt6.dashboard.widgets.llm_status_widget import LLMStatusWidget
        monkeypatch.setattr(LLMStatusWidget, "play_success", lambda self: None, raising=False)
        w = LLMStatusWidget("LLM", bridge=None)
        w.update_data({"enabled": True})
        assert w._status_label.text() != ""
        w.update_data({"enabled": False})
        assert w._status_label.text() != ""


class TestDashboardPage:
    """Test DashboardPage layout, drag events, and widget creation."""

    def test_resolve_config_path_returns_path(self, tmp_path: Path, qapp: QApplication) -> None:
        page = DashboardPage(bridge=None)
        assert isinstance(page._resolve_config_path(), Path)

    def test_setup_ui_creates_grid_and_buttons(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        from gui.pyqt6.i18n import get_locale_manager
        import core.foundation.paths as _paths

        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)
        monkeypatch.setattr(_paths, "get_project_root", lambda: tmp_path)
        page = DashboardPage(bridge=None)
        assert page._grid is not None
        assert hasattr(page, "_add_widget")

    def test_add_default_widgets_when_no_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        from gui.pyqt6.i18n import get_locale_manager
        import core.foundation.paths as _paths

        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)
        monkeypatch.setattr(_paths, "get_project_root", lambda: tmp_path)
        page = DashboardPage(bridge=None)
        assert len(page._grid_widgets) == 4
        assert "device" in page._grid_widgets
        assert "queue" in page._grid_widgets

    def test_load_layout_from_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        from gui.pyqt6.i18n import get_locale_manager
        import core.foundation.paths as _paths

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_path = config_dir / "dashboard_layout.json"
        config_path.write_text(
            json.dumps({"widgets": [{"id": "device", "row": 0, "col": 0, "title": "Device"}]}, ensure_ascii=False),
            encoding="utf-8",
        )
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)
        monkeypatch.setattr(_paths, "get_project_root", lambda: tmp_path)
        page = DashboardPage(bridge=None)
        assert "device" in page._grid_widgets

    def test_drag_enter_and_move_accept_dashboard_widget(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        from gui.pyqt6.i18n import get_locale_manager
        import core.foundation.paths as _paths

        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)
        monkeypatch.setattr(_paths, "get_project_root", lambda: tmp_path)
        page = DashboardPage(bridge=None)
        from PyQt6.QtCore import QMimeData
        mime = QMimeData()
        mime.setData("application/x-dashboard-widget", b"device")

        class FakeEvent:
            def mimeData(self):
                return mime
            def accept(self):
                pass
            def ignore(self):
                pass

        event = FakeEvent()
        page.dragEnterEvent(event)
        page.dragMoveEvent(event)

    def test_drop_event_ignores_unknown_format(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> None:
        from gui.pyqt6.i18n import get_locale_manager
        import core.foundation.paths as _paths

        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)
        monkeypatch.setattr(_paths, "get_project_root", lambda: tmp_path)
        page = DashboardPage(bridge=None)
        from PyQt6.QtCore import QMimeData
        mime = QMimeData()
        mime.setData("application/unknown", b"x")

        class FakeEvent:
            def mimeData(self):
                return mime
            def accept(self):
                pass
            def ignore(self):
                pass

        event = FakeEvent()
        page.dropEvent(event)


class TestWidgetMarketDialog:
    """Test WidgetMarketDialog UI and selection."""

    def test_setup_ui_populates_list(self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
        from gui.pyqt6.i18n import get_locale_manager
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)
        dialog = WidgetMarketDialog(bridge=None)
        items = [dialog._widget_list.item(i).text() for i in range(dialog._widget_list.count())]
        assert len(items) > 0

    def test_on_selection_changed_sets_id(self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
        from gui.pyqt6.i18n import get_locale_manager
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)
        dialog = WidgetMarketDialog(bridge=None)
        dialog._widget_list.setCurrentRow(dialog._widget_list.count() - 1)
        dialog._on_selection_changed()
        assert dialog.selected_widget_id() is not None

    def test_selected_widget_id_none_when_no_selection(self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
        from gui.pyqt6.i18n import get_locale_manager
        monkeypatch.setattr(get_locale_manager(), "tr", lambda key, default="": default)
        dialog = WidgetMarketDialog(bridge=None)
        assert dialog.selected_widget_id() is None
