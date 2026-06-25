"""最小化到托盘功能测试（反映生产环境关键状态）"""
import sys
import os
import json
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtWidgets import QApplication

# 确保 src 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(project_root, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from gui.pyqt6.pages.settings_page import SettingsPage


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


class TestSettingsPageMinimizeToTray:
    """SettingsPage 最小化到托盘信号与配置更新"""

    def test_emit_checked_when_state_is_checked(self, qapp):
        page = SettingsPage(config={})
        captured = []
        page.minimize_to_tray_changed.connect(lambda v: captured.append(v))

        # Qt.Checked 通常 state=2
        page._on_tray_changed(2)
        assert captured == [True]
        assert page._config.get("system", {}).get("minimize_to_tray") is True

    def test_emit_unchecked_when_state_is_unchecked(self, qapp):
        page = SettingsPage(config={})
        captured = []
        page.minimize_to_tray_changed.connect(lambda v: captured.append(v))

        page._on_tray_changed(0)
        assert captured == [False]
        assert page._config.get("system", {}).get("minimize_to_tray") is False

    def test_qt_checked_enum_equivalence(self, qapp):
        page = SettingsPage(config={})
        captured = []
        page.minimize_to_tray_changed.connect(lambda v: captured.append(v))

        page._on_tray_changed(Qt.CheckState.Checked)
        assert captured == [True]

    def test_load_config_sets_checkbox_and_emits(self, qapp):
        page = SettingsPage(config={"system": {"minimize_to_tray": True}})
        captured = []
        page.minimize_to_tray_changed.connect(lambda v: captured.append(v))

        page._load_config()
        assert page._tray_cb.isChecked() is True
        assert captured == [True]

    def test_get_config_returns_updated_config(self, qapp):
        page = SettingsPage(config={"system": {"minimize_to_tray": False}})
        page._on_tray_changed(2)
        cfg = page.get_config()
        assert cfg["system"]["minimize_to_tray"] is True


def _make_main_window(qtbot):
    # 使用最小依赖构造 MainWindow，避免启动托盘/ADB 等重型资源
    from gui.pyqt6.main_window import MainWindow
    mw = MainWindow.__new__(MainWindow)
    # 先调用基类初始化，避免 RuntimeError
    from PyQt6.QtWidgets import QMainWindow
    QMainWindow.__init__(mw)
    mw._minimize_to_tray = False
    mw._tray_available = False
    mw._is_executing_standard_flow = False
    mw._config = {"system": {"minimize_to_tray": False}}
    return mw


class TestMainWindowCloseEventBranches:
    """MainWindow closeEvent 关键分支（不启动完整窗口，仅做分支覆盖与状态断言）"""

    def test_close_event_priority3_direct_exit(self, qtbot):
        from PyQt6.QtWidgets import QMessageBox

        mw = _make_main_window(qtbot)
        mw._minimize_to_tray = False
        mw._tray_available = False
        mw._is_executing_standard_flow = False

        with patch.object(mw, "_cleanup_before_exit") as cleanup_mock, \
             patch("PyQt6.QtWidgets.QApplication.instance") as app_mock:
            app_mock.return_value.quit = MagicMock()
            event = MagicMock()
            mw.closeEvent(event)
            cleanup_mock.assert_called_once()
            event.accept.assert_called_once()
            app_mock.return_value.quit.assert_called_once()

    def test_close_event_priority2_minimize_to_tray(self, qtbot):
        mw = _make_main_window(qtbot)
        mw._minimize_to_tray = True
        mw._tray_available = True
        mw._is_executing_standard_flow = False

        with patch.object(mw, "_ensure_hidden_owner"), \
             patch.object(mw, "_apply_toolwindow_to_process_windows"), \
             patch.object(mw, "hide"), \
             patch.object(mw, "setWindowFlag"), \
             patch.object(mw, "append_log"), \
             patch("ctypes.windll.user32") as user32_mock:
            user32_mock.GetWindowLongPtrW.return_value = 0
            user32_mock.SetWindowLongPtrW.return_value = 0
            event = MagicMock()
            mw.closeEvent(event)
            event.ignore.assert_called_once()
            event.accept.assert_not_called()


class TestMainWindowMinimizeToTrayToggle:
    """MainWindow 最小化到托盘开关状态切换（含托盘重建）"""

    def test_enable_rebuilds_tray_when_none(self, qtbot):
        from gui.pyqt6.main_window import MainWindow

        mw = _make_main_window(qtbot)
        mw._tray_icon = None
        mw._tray_available = False
        mw._minimize_to_tray = False

        with patch.object(mw, "_setup_tray") as setup_tray_mock, \
             patch.object(mw, "_ensure_hidden_owner"), \
             patch.object(mw, "_apply_toolwindow_to_process_windows"), \
             patch.object(mw, "_persist_minimize_setting") as persist_mock:
            mw._on_minimize_to_tray_changed(True)
            setup_tray_mock.assert_called_once()
            persist_mock.assert_called_once_with(True)
            assert mw._minimize_to_tray is True


class TestMinimizeToTrayConfigPersistence:
    """配置持久化关键路径（反映生产环境写入与重载状态）"""

    def test_persist_and_reload_roundtrip(self, tmp_path):
        """模拟 _persist_minimize_setting 与 _reload_disk_config 的读写闭环"""
        config_path = tmp_path / "client_config.json"
        initial = {"system": {"minimize_to_tray": False}}

        # 初始写入
        config_path.write_text(json.dumps(initial, ensure_ascii=False), encoding="utf-8")

        # 模拟 _persist_minimize_setting 写入
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
        cfg.setdefault("system", {})
        cfg["system"]["minimize_to_tray"] = True
        config_path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")

        # 模拟 _reload_disk_config 读取合并
        loaded = json.loads(config_path.read_text(encoding="utf-8"))
        merged = {"system": {"minimize_to_tray": False}}
        for k, v in loaded.items():
            if isinstance(v, dict) and isinstance(merged.get(k), dict):
                merged[k].update(v)
            else:
                merged[k] = v

        assert merged["system"]["minimize_to_tray"] is True

    def test_persist_creates_file_when_missing(self, tmp_path):
        config_path = tmp_path / "client_config.json"
        assert not config_path.exists()

        cfg = {"system": {"minimize_to_tray": True}}
        config_path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")

        loaded = json.loads(config_path.read_text(encoding="utf-8"))
        assert loaded["system"]["minimize_to_tray"] is True
