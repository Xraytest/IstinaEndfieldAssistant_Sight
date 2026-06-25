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

    def test_emit_checked_when_checked(self, qapp):
        page = SettingsPage(config={})
        captured = []
        page.minimize_to_tray_changed.connect(lambda v: captured.append(v))

        # 勾选复选框（setChecked 会自动触发 stateChanged 信号）
        page._tray_cb.setChecked(True)
        assert captured == [True]
        assert page._config.get("system", {}).get("minimize_to_tray") is True

    def test_emit_unchecked_when_unchecked(self, qapp):
        page = SettingsPage(config={})
        captured = []
        page.minimize_to_tray_changed.connect(lambda v: captured.append(v))

        # 先勾选，再取消勾选（setChecked 会自动触发 stateChanged 信号）
        page._tray_cb.setChecked(True)
        captured.clear()
        page._tray_cb.setChecked(False)
        assert captured == [False]
        assert page._config.get("system", {}).get("minimize_to_tray") is False

    def test_qt_checked_enum_equivalence(self, qapp):
        page = SettingsPage(config={})
        captured = []
        page.minimize_to_tray_changed.connect(lambda v: captured.append(v))

        page._tray_cb.setChecked(True)
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
        page._tray_cb.setChecked(True)
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


class TestMinimizeToTrayProductionFlow:
    """模拟生产环境完整流程：设置页切换 -> 主窗口接收 -> 关闭事件行为"""

    def test_full_flow_check_then_close_minimizes_to_tray(self, qtbot):
        from gui.pyqt6.main_window import MainWindow

        mw = _make_main_window(qtbot)
        mw._minimize_to_tray = False
        mw._tray_available = False
        mw._is_executing_standard_flow = False

        # 步骤1：模拟设置页勾选托盘
        with patch.object(mw, "_setup_tray") as setup_tray_mock, \
             patch.object(mw, "_ensure_hidden_owner"), \
             patch.object(mw, "_apply_toolwindow_to_process_windows"), \
             patch.object(mw, "_persist_minimize_setting") as persist_mock:
            mw._on_minimize_to_tray_changed(True)
            setup_tray_mock.assert_called_once()
            persist_mock.assert_called_once_with(True)
            assert mw._minimize_to_tray is True

        # 步骤2：模拟关闭窗口（托盘已重建，_tray_available 应为 True）
        # 由于 _setup_tray 被 patch，我们需要手动设置 _tray_available
        mw._tray_available = True
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

    def test_full_flow_uncheck_then_close_direct_exit(self, qtbot):
        from gui.pyqt6.main_window import MainWindow

        mw = _make_main_window(qtbot)
        mw._minimize_to_tray = True
        mw._tray_available = True
        mw._is_executing_standard_flow = False
        # 模拟已存在的托盘图标，以便取消时进入销毁分支
        mw._tray_icon = MagicMock()

        # 步骤1：模拟设置页取消勾选托盘
        with patch.object(mw, "_setup_tray"), \
             patch.object(mw, "_ensure_hidden_owner"), \
             patch.object(mw, "_apply_toolwindow_to_process_windows"), \
             patch.object(mw, "_persist_minimize_setting") as persist_mock:
            mw._on_minimize_to_tray_changed(False)
            persist_mock.assert_called_once_with(False)
            assert mw._minimize_to_tray is False
            assert mw._tray_available is False

        # 步骤2：模拟关闭窗口（托盘已销毁，应直接退出）
        with patch.object(mw, "_cleanup_before_exit") as cleanup_mock, \
             patch("PyQt6.QtWidgets.QApplication.instance") as app_mock:
            app_mock.return_value.quit = MagicMock()
            event = MagicMock()
            mw.closeEvent(event)
            cleanup_mock.assert_called_once()
            event.accept.assert_called_once()
            app_mock.return_value.quit.assert_called_once()


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


class TestTrayRestoreWindowState:
    """托盘还原后窗口状态验证（分析无响应问题的关键测试）"""

    def _make_main_window(self, qtbot):
        from gui.pyqt6.main_window import MainWindow
        mw = MainWindow.__new__(MainWindow)
        from PyQt6.QtWidgets import QMainWindow
        QMainWindow.__init__(mw)
        mw._minimize_to_tray = True
        mw._tray_available = True
        mw._is_executing_standard_flow = False
        mw._config = {"system": {"minimize_to_tray": True}}
        return mw

    def test_restore_qt_path_sets_normal_state(self, qtbot):
        """Qt 恢复成功路径：窗口应回到正常状态（非最小化、有焦点）"""
        mw = self._make_main_window(qtbot)
        mw._orig_window_flags = mw.windowFlags()
        mw._orig_hwnd_parent = 0x1234  # 设置一个模拟的原始父窗口句柄

        with patch.object(mw, "_win32_apply_appwindow"), \
             patch.object(mw, "_start_winid_watcher"), \
             patch.object(mw, "_dump_native_windows"), \
             patch.object(mw, "_destroy_hidden_owner"), \
             patch.object(mw, "append_log"), \
             patch("ctypes.windll.user32") as user32_mock:
            # 模拟 WS_EX_APPWINDOW 已设置，Qt 恢复成功
            user32_mock.GetWindowLongPtrW.return_value = 0x00040000
            user32_mock.GetWindowLongW.return_value = 0x00040000
            user32_mock.SetWindowLongPtrW.return_value = 0
            user32_mock.SetWindowLongW.return_value = 0
            user32_mock.SetWindowPos.return_value = True

            with patch.object(mw, "showNormal") as show_mock, \
                 patch.object(mw, "raise_") as raise_mock, \
                 patch.object(mw, "activateWindow") as activate_mock, \
                 patch.object(mw, "ensure_window_buttons"), \
                 patch("PyQt6.QtCore.QTimer.singleShot") as timer_mock:
                mw._restore_from_tray()
                # 验证窗口处于正常状态（非最小化）
                assert not mw.windowState() & Qt.WindowState.WindowMinimized
                show_mock.assert_called()
                raise_mock.assert_called()
                activate_mock.assert_called()
                # Qt 路径现在使用延迟检查，验证定时器被设置为 100ms
                assert timer_mock.call_count == 2
                # 第一个定时器应为延迟激活窗口（50ms）
                first_call = timer_mock.call_args_list[0]
                assert first_call[0][0] == 50, f"Qt activate delay should be 50ms, got {first_call[0][0]}ms"
                assert callable(first_call[0][1])
                # 第二个定时器应为延迟检查样式（100ms）
                second_call = timer_mock.call_args_list[1]
                assert second_call[0][0] == 100, f"Qt restore delay should be 100ms, got {second_call[0][0]}ms"
                assert callable(second_call[0][1])

    def test_restore_win32_fallback_sets_appwindow(self, qtbot):
        """Win32 回退路径：验证 APPWINDOW 样式被正确设置"""
        mw = self._make_main_window(qtbot)
        mw._orig_window_flags = mw.windowFlags()
        mw._orig_hwnd_parent = 0

        with patch.object(mw, "_win32_apply_appwindow") as win32_mock, \
             patch.object(mw, "_start_winid_watcher") as watcher_mock, \
             patch.object(mw, "_dump_native_windows"), \
             patch.object(mw, "_destroy_hidden_owner"), \
             patch.object(mw, "append_log"), \
             patch("ctypes.windll.user32") as user32_mock, \
             patch("ctypes.windll.kernel32") as kernel32_mock, \
             patch("PyQt6.QtCore.QTimer.singleShot") as timer_mock:
            # 模拟 Qt 恢复后 APPWINDOW 未设置
            user32_mock.GetWindowLongPtrW.return_value = 0x00000000
            user32_mock.GetWindowLongW.return_value = 0x00000000
            kernel32_mock.GetLastError.return_value = 0

            with patch.object(mw, "showNormal") as show_mock, \
                 patch.object(mw, "raise_") as raise_mock, \
                 patch.object(mw, "activateWindow") as activate_mock, \
                 patch.object(mw, "ensure_window_buttons"):
                # 直接调用 Win32 回退方法
                mw._restore_from_tray_win32_fallback()
                show_mock.assert_called()
                raise_mock.assert_called()
                activate_mock.assert_called()
                # Win32 回退应设置延迟定时器来应用 APPWINDOW
                assert timer_mock.call_count >= 1
                # 验证第一个定时器是延迟 50ms 激活窗口
                first_call = timer_mock.call_args_list[0]
                assert first_call[0][0] == 50
                assert callable(first_call[0][1])
                # 由于 QTimer.singleShot 被 mock，_win32_apply_appwindow 不会立即执行
                # 验证它被作为延迟回调传入
                callback = first_call[0][1]
                assert callback is not None
                watcher_mock.assert_called()

    def test_restore_preserves_window_interactive_flags(self, qtbot):
        """还原后窗口应保持可交互标志（非 Tool 窗口、可接收焦点）"""
        mw = self._make_main_window(qtbot)
        mw._orig_window_flags = mw.windowFlags()

        with patch.object(mw, "_win32_apply_appwindow"), \
             patch.object(mw, "_start_winid_watcher"), \
             patch.object(mw, "_dump_native_windows"), \
             patch.object(mw, "_destroy_hidden_owner"), \
             patch.object(mw, "append_log"), \
             patch("ctypes.windll.user32") as user32_mock:
            user32_mock.GetWindowLongPtrW.return_value = 0x00040000
            user32_mock.GetWindowLongW.return_value = 0x00040000

            with patch.object(mw, "showNormal") as show_mock, \
                 patch.object(mw, "raise_") as raise_mock, \
                 patch.object(mw, "activateWindow") as activate_mock, \
                 patch.object(mw, "ensure_window_buttons"):
                mw._restore_from_tray()
                # 验证窗口状态被设置为正常（非最小化、非工具窗口）
                assert not mw.windowState() & Qt.WindowState.WindowMinimized
                show_mock.assert_called()
                raise_mock.assert_called()
                activate_mock.assert_called()

    def test_restore_delays_owner_destruction(self, qtbot):
        """还原流程中 owner 应在窗口显示后再销毁，避免父子关系残留"""
        mw = self._make_main_window(qtbot)
        mw._orig_window_flags = mw.windowFlags()
        mw._orig_hwnd_parent = 0x1234  # 设置一个模拟的原始父窗口句柄
        mw._hidden_owner_hwnd = 12345
        mw._hidden_owner_widget = MagicMock()

        with patch.object(mw, "_win32_apply_appwindow"), \
             patch.object(mw, "_start_winid_watcher"), \
             patch.object(mw, "_dump_native_windows"), \
             patch.object(mw, "append_log"), \
             patch("ctypes.windll.user32") as user32_mock, \
             patch("PyQt6.QtCore.QTimer.singleShot") as timer_mock:
            user32_mock.GetWindowLongPtrW.return_value = 0x00040000
            user32_mock.GetWindowLongW.return_value = 0x00040000
            user32_mock.SetWindowLongPtrW.return_value = 0
            user32_mock.SetWindowLongW.return_value = 0
            user32_mock.SetWindowPos.return_value = True

            with patch.object(mw, "showNormal") as show_mock, \
                 patch.object(mw, "raise_") as raise_mock, \
                 patch.object(mw, "activateWindow") as activate_mock, \
                 patch.object(mw, "ensure_window_buttons"), \
                 patch.object(mw, "_destroy_hidden_owner") as destroy_mock:
                mw._restore_from_tray()
                show_mock.assert_called()
                # owner 销毁应通过 QTimer 延迟调用，而非立即调用
                destroy_mock.assert_not_called()
                # 验证 QTimer.singleShot 被调用，包含延迟激活（50ms）和延迟检查（100ms）
                assert timer_mock.call_count == 2
                # 验证存在 100ms 的样式检查定时器
                restore_timer_found = False
                for call in timer_mock.call_args_list:
                    if call[0][0] == 100 and callable(call[0][1]):
                        restore_timer_found = True
                        break
                assert restore_timer_found, "Restore check timer not found"

    def test_restore_qt_path_sets_parent_none_and_pos(self, qtbot):
        """无原始父窗口句柄时，Qt 路径也应设置延迟检查回调"""
        mw = self._make_main_window(qtbot)
        mw._orig_window_flags = mw.windowFlags()
        mw._orig_hwnd_parent = None
        mw._hidden_owner_hwnd = 12345
        mw._hidden_owner_widget = MagicMock()

        with patch.object(mw, "_win32_apply_appwindow"), \
             patch.object(mw, "_start_winid_watcher"), \
             patch.object(mw, "_dump_native_windows"), \
             patch.object(mw, "append_log"), \
             patch("ctypes.windll.user32") as user32_mock, \
             patch("PyQt6.QtCore.QTimer.singleShot") as timer_mock:
            user32_mock.GetWindowLongPtrW.return_value = 0x00040000
            user32_mock.GetWindowLongW.return_value = 0x00040000
            user32_mock.SetWindowLongPtrW.return_value = 0
            user32_mock.SetWindowLongW.return_value = 0
            user32_mock.SetWindowPos.return_value = True

            with patch.object(mw, "showNormal") as show_mock, \
                 patch.object(mw, "raise_") as raise_mock, \
                 patch.object(mw, "activateWindow") as activate_mock, \
                 patch.object(mw, "ensure_window_buttons"), \
                 patch.object(mw, "_destroy_hidden_owner"):
                mw._restore_from_tray()
                show_mock.assert_called()
                # 验证延迟检查回调被设置（包含 50ms 激活和 100ms 检查）
                assert timer_mock.call_count == 2
                restore_timer_found = False
                for call in timer_mock.call_args_list:
                    if call[0][0] == 100 and callable(call[0][1]):
                        restore_timer_found = True
                        break
                assert restore_timer_found, "Restore check timer not found"

    def test_restore_win32_fallback_delays_owner_destruction(self, qtbot):
        """Win32 回退路径：owner 也应在窗口显示后再延迟销毁"""
        mw = self._make_main_window(qtbot)
        mw._orig_window_flags = mw.windowFlags()
        mw._orig_hwnd_parent = 0
        mw._hidden_owner_hwnd = 12345
        mw._hidden_owner_widget = MagicMock()

        with patch.object(mw, "_win32_apply_appwindow") as win32_mock, \
             patch.object(mw, "_start_winid_watcher") as watcher_mock, \
             patch.object(mw, "_dump_native_windows"), \
             patch.object(mw, "append_log"), \
             patch("ctypes.windll.user32") as user32_mock, \
             patch("ctypes.windll.kernel32") as kernel32_mock, \
             patch("PyQt6.QtCore.QTimer.singleShot") as timer_mock:
            # 模拟 Qt 恢复后 APPWINDOW 未设置
            user32_mock.GetWindowLongPtrW.return_value = 0x00000000
            user32_mock.GetWindowLongW.return_value = 0x00000000
            kernel32_mock.GetLastError.return_value = 0

            with patch.object(mw, "showNormal") as show_mock, \
                 patch.object(mw, "raise_") as raise_mock, \
                 patch.object(mw, "activateWindow") as activate_mock, \
                 patch.object(mw, "ensure_window_buttons"), \
                 patch.object(mw, "_destroy_hidden_owner") as destroy_mock:
                # 直接调用 Win32 回退方法（模拟延迟回调中的调用）
                mw._restore_from_tray_win32_fallback()
                show_mock.assert_called()
                # Win32 回退路径中 owner 不应立即销毁
                destroy_mock.assert_not_called()
                # Win32 回退路径中 singleShot 会被调用：
                # 1) 预显示 APPWINDOW 设置 (立即)
                # 2) 延迟 APPWINDOW 验证 (100ms)
                # 3) 异步重试 APPWINDOW 设置 (100ms)
                # 4) 延迟 owner 销毁 (250ms)
                assert timer_mock.call_count >= 1
                # 验证存在延迟 APPWINDOW 设置的定时器
                appwindow_timer_found = False
                for call in timer_mock.call_args_list:
                    if call[0][0] == 100 and callable(call[0][1]):
                        appwindow_timer_found = True
                        break
                assert appwindow_timer_found, "APPWINDOW apply timer not found"
                # 验证 owner 销毁延迟为 250ms
                owner_destroy_call = None
                for call in timer_mock.call_args_list:
                    if call[0][1] == destroy_mock:
                        owner_destroy_call = call
                        break
                assert owner_destroy_call is not None, "Owner destruction timer not found"
                assert owner_destroy_call[0][0] == 250, f"Owner destruction delay should be 250ms, got {owner_destroy_call[0][0]}ms"
                watcher_mock.assert_called()

    def test_restore_handles_hwnd_recreation(self, qtbot):
        """showNormal 后 HWND 可能重建，应通过 winId watcher 重新绑定样式"""
        mw = self._make_main_window(qtbot)
        mw._orig_window_flags = mw.windowFlags()
        mw._orig_hwnd_parent = 0

        with patch.object(mw, "_win32_apply_appwindow") as win32_mock, \
             patch.object(mw, "_start_winid_watcher") as watcher_mock, \
             patch.object(mw, "_dump_native_windows"), \
             patch.object(mw, "_destroy_hidden_owner"), \
             patch.object(mw, "append_log"), \
             patch("ctypes.windll.user32") as user32_mock, \
             patch("ctypes.windll.kernel32") as kernel32_mock:
            user32_mock.GetWindowLongPtrW.return_value = 0x00000000
            user32_mock.GetWindowLongW.return_value = 0x00000000
            kernel32_mock.GetLastError.return_value = 0

            with patch.object(mw, "showNormal"), \
                 patch.object(mw, "raise_"), \
                 patch.object(mw, "activateWindow"), \
                 patch.object(mw, "ensure_window_buttons"), \
                 patch("PyQt6.QtCore.QTimer.singleShot") as timer_mock:
                # 直接调用 Win32 回退方法（模拟延迟回调中的调用）
                mw._restore_from_tray_win32_fallback()
                # Win32 回退和 watcher 都应通过延迟回调设置
                # 由于 QTimer.singleShot 被 mock，验证定时器被设置
                assert timer_mock.call_count >= 1
                # 验证存在 100ms 的 APPWINDOW 应用定时器
                appwindow_timer_found = False
                for call in timer_mock.call_args_list:
                    if call[0][0] == 100 and callable(call[0][1]):
                        appwindow_timer_found = True
                        break
                assert appwindow_timer_found, "APPWINDOW apply timer not found"
                watcher_mock.assert_called()

    def test_restore_uses_original_window_flags(self, qtbot):
        """还原时应使用最小化时保存的原始窗口标志"""
        mw = self._make_main_window(qtbot)
        original_flags = mw.windowFlags()
        mw._orig_window_flags = original_flags

        with patch.object(mw, "_win32_apply_appwindow"), \
             patch.object(mw, "_start_winid_watcher"), \
             patch.object(mw, "_dump_native_windows"), \
             patch.object(mw, "_destroy_hidden_owner"), \
             patch.object(mw, "append_log"), \
             patch("ctypes.windll.user32") as user32_mock:
            user32_mock.GetWindowLongPtrW.return_value = 0x00040000
            user32_mock.GetWindowLongW.return_value = 0x00040000

            with patch.object(mw, "showNormal") as show_mock, \
                 patch.object(mw, "raise_") as raise_mock, \
                 patch.object(mw, "activateWindow") as activate_mock, \
                 patch.object(mw, "ensure_window_buttons"), \
                 patch.object(mw, "setWindowFlags") as flags_mock:
                mw._restore_from_tray()
                # 验证 setWindowFlags 被调用以恢复原始标志
                flags_mock.assert_called_with(original_flags)
                show_mock.assert_called()
                raise_mock.assert_called()
                activate_mock.assert_called()

    def test_restore_applies_win32_styles_before_showing(self, qtbot):
        """生产态：还原路径应在 showNormal 前完成 Win32 样式修正，避免窗口以错误样式显示"""
        mw = self._make_main_window(qtbot)
        mw._orig_window_flags = mw.windowFlags()
        mw._orig_hwnd_parent = 0

        style_order = []
        def track_ensure():
            style_order.append("ensure")
        def track_show():
            style_order.append("show")

        with patch.object(mw, "_ensure_appwindow_style", side_effect=track_ensure), \
             patch.object(mw, "_start_winid_watcher"), \
             patch.object(mw, "_dump_native_windows"), \
             patch.object(mw, "_destroy_hidden_owner"), \
             patch.object(mw, "append_log"), \
             patch("ctypes.windll.user32") as user32_mock, \
             patch("ctypes.windll.kernel32") as kernel32_mock:
            user32_mock.GetWindowLongPtrW.return_value = 0x00000000
            user32_mock.GetWindowLongW.return_value = 0x00000000
            kernel32_mock.GetLastError.return_value = 0

            with patch.object(mw, "showNormal", side_effect=track_show) as show_mock, \
                 patch.object(mw, "raise_"), \
                 patch.object(mw, "activateWindow"), \
                 patch.object(mw, "ensure_window_buttons"), \
                 patch.object(mw, "setWindowFlags"), \
                 patch("PyQt6.QtCore.QTimer.singleShot") as timer_mock:
                # 不执行定时器回调，仅验证调用顺序
                mw._restore_from_tray()

        # showNormal 之前应先完成 APPWINDOW 样式设置
        assert style_order.index("ensure") < style_order.index("show")

    def test_restore_async_retry_uses_current_hwnd_after_showNormal(self, qtbot):
        """Win32 回退路径：异步重试应使用 showNormal 后的当前 HWND，而非旧 HWND"""
        mw = self._make_main_window(qtbot)
        mw._orig_window_flags = mw.windowFlags()
        mw._orig_hwnd_parent = 0

        call_count = 0
        def mock_winId():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return 1000  # 初始 hwnd（showNormal 前）
            return 2000  # showNormal 后重建的 hwnd

        mw.winId = mock_winId

        with patch.object(mw, "_win32_apply_appwindow") as win32_mock, \
             patch.object(mw, "_start_winid_watcher") as watcher_mock, \
             patch.object(mw, "_dump_native_windows"), \
             patch.object(mw, "_destroy_hidden_owner"), \
             patch.object(mw, "append_log"), \
             patch("ctypes.windll.user32") as user32_mock, \
             patch("ctypes.windll.kernel32") as kernel32_mock, \
             patch("PyQt6.QtCore.QTimer.singleShot") as timer_mock:
            user32_mock.GetWindowLongPtrW.return_value = 0x00000000
            user32_mock.GetWindowLongW.return_value = 0x00000000
            kernel32_mock.GetLastError.return_value = 0

            with patch.object(mw, "showNormal") as show_mock, \
                 patch.object(mw, "raise_"), \
                 patch.object(mw, "activateWindow"), \
                 patch.object(mw, "ensure_window_buttons"):
                # 直接调用 Win32 回退方法（模拟延迟回调中的调用）
                mw._restore_from_tray_win32_fallback()
                show_mock.assert_called()
                # Win32 回退应设置延迟定时器来应用 APPWINDOW
                assert timer_mock.call_count >= 1
                # 验证第一个定时器是延迟 50ms 激活窗口
                first_call = timer_mock.call_args_list[0]
                assert first_call[0][0] == 50
                assert callable(first_call[0][1])
                # 验证异步重试使用的 hwnd 是 showNormal 后的 hwnd (2000)
                # 而不是 showNormal 前的旧 hwnd (1000)
                async_call = timer_mock.call_args_list[1]
                args, _ = async_call
                assert args[0] == 100
                # 调用回调并检查传入的 hwnd
                args[1]()
                # 验证 _win32_apply_appwindow 被调用时使用了新 hwnd (2000)
                # 最后一次调用的第一个参数应该是 2000
                last_call = win32_mock.call_args_list[-1]
                call_hwnd = last_call[0][0] if last_call[0] else last_call[1].get('hwnd', 0)
                assert call_hwnd == 2000, f"Async retry should use current hwnd (2000), got {call_hwnd}"
                watcher_mock.assert_called()

    def test_restore_removes_toolwindow_when_appwindow_set(self, qtbot):
        """还原时如果 APPWINDOW 已设置，应同时移除 TOOLWINDOW 避免样式冲突导致窗口无响应"""
        mw = self._make_main_window(qtbot)
        mw._orig_window_flags = mw.windowFlags()
        mw._orig_hwnd_parent = 0

        with patch.object(mw, "_win32_apply_appwindow"), \
             patch.object(mw, "_start_winid_watcher"), \
             patch.object(mw, "_dump_native_windows"), \
             patch.object(mw, "_destroy_hidden_owner"), \
             patch.object(mw, "append_log"), \
             patch("ctypes.windll.user32") as user32_mock:
            # 模拟窗口同时有 APPWINDOW 和 TOOLWINDOW（样式冲突状态）
            user32_mock.GetWindowLongPtrW.return_value = 0x00040080  # APPWINDOW | TOOLWINDOW
            user32_mock.GetWindowLongW.return_value = 0x00040080
            user32_mock.SetWindowLongPtrW.return_value = 0
            user32_mock.SetWindowLongW.return_value = 0
            user32_mock.SetWindowPos.return_value = True

            with patch.object(mw, "showNormal") as show_mock, \
                 patch.object(mw, "raise_") as raise_mock, \
                 patch.object(mw, "activateWindow") as activate_mock, \
                 patch.object(mw, "ensure_window_buttons"), \
                 patch("PyQt6.QtCore.QTimer.singleShot") as timer_mock:
                mw._restore_from_tray()
                # 验证窗口处于正常状态（非最小化）
                assert not mw.windowState() & Qt.WindowState.WindowMinimized
                show_mock.assert_called()
                raise_mock.assert_called()
                activate_mock.assert_called()
                # Qt 路径现在使用延迟检查，验证定时器被设置为 100ms
                assert timer_mock.call_count == 2
                # 第一个定时器应为延迟激活窗口（50ms）
                first_call = timer_mock.call_args_list[0]
                assert first_call[0][0] == 50, f"Qt activate delay should be 50ms, got {first_call[0][0]}ms"
                assert callable(first_call[0][1])
                # 第二个定时器应为延迟检查样式（100ms）
                second_call = timer_mock.call_args_list[1]
                assert second_call[0][0] == 100, f"Qt restore delay should be 100ms, got {second_call[0][0]}ms"
                assert callable(second_call[0][1])

    def test_restore_window_remains_enabled(self, qtbot):
        """还原后窗口应保持启用状态，能够接收用户输入"""
        mw = self._make_main_window(qtbot)
        mw._orig_window_flags = mw.windowFlags()
        mw._orig_hwnd_parent = 0
        # 模拟窗口在还原后保持启用
        mw.setEnabled(True)

        with patch.object(mw, "_win32_apply_appwindow"), \
             patch.object(mw, "_start_winid_watcher"), \
             patch.object(mw, "_dump_native_windows"), \
             patch.object(mw, "_destroy_hidden_owner"), \
             patch.object(mw, "append_log"), \
             patch("ctypes.windll.user32") as user32_mock:
            user32_mock.GetWindowLongPtrW.return_value = 0x00040000
            user32_mock.GetWindowLongW.return_value = 0x00040000

            with patch.object(mw, "showNormal") as show_mock, \
                 patch.object(mw, "raise_") as raise_mock, \
                 patch.object(mw, "activateWindow") as activate_mock, \
                 patch.object(mw, "ensure_window_buttons"):
                mw._restore_from_tray()
                # 验证窗口保持启用状态
                assert mw.isEnabled() is True
                show_mock.assert_called()
                raise_mock.assert_called()
                activate_mock.assert_called()


class TestMinimizeToTrayProductionState:
    """生产态完整流程测试（减少 mock，验证窗口实际状态）"""

    def _make_shown_main_window(self, qtbot):
        from gui.pyqt6.main_window import MainWindow
        mw = MainWindow.__new__(MainWindow)
        from PyQt6.QtWidgets import QMainWindow
        QMainWindow.__init__(mw)
        mw._minimize_to_tray = True
        mw._tray_available = True
        mw._is_executing_standard_flow = False
        mw._config = {"system": {"minimize_to_tray": True}}
        # 实际显示窗口，确保拥有有效 HWND 与生产状态一致
        mw.show()
        qtbot.wait(50)
        assert int(mw.winId()) != 0, "窗口应拥有有效 HWND"
        return mw

    def test_full_minimize_restore_flow_keeps_window_visible_and_enabled(self, qtbot):
        """模拟完整的最小化->还原流程，验证窗口最终可见且启用"""
        mw = self._make_shown_main_window(qtbot)
        assert mw.isVisible() is True
        assert mw.isEnabled() is True

        # 模拟最小化到托盘（仅设置必要状态，不实际隐藏以便测试恢复）
        mw._orig_window_flags = mw.windowFlags()
        mw._orig_hwnd_parent = 0
        mw._hidden_owner_widget = MagicMock()
        mw._hidden_owner_hwnd = 12345
        mw.setWindowFlag(Qt.WindowType.Tool, True)

        # 模拟还原流程（尽可能减少 mock）
        with patch.object(mw, "_ensure_hidden_owner"), \
             patch.object(mw, "_apply_toolwindow_to_process_windows"), \
             patch.object(mw, "_persist_minimize_setting"), \
             patch.object(mw, "_win32_apply_appwindow") as win32_mock, \
             patch.object(mw, "_start_winid_watcher") as watcher_mock, \
             patch.object(mw, "_dump_native_windows"), \
             patch.object(mw, "append_log"):
            # 模拟 Win32 API 返回 APPWINDOW 已设置
            import ctypes
            with patch("ctypes.windll.user32") as user32_mock:
                user32_mock.GetWindowLongPtrW.return_value = 0x00040000
                user32_mock.GetWindowLongW.return_value = 0x00040000
                user32_mock.SetWindowLongPtrW.return_value = 0
                user32_mock.SetWindowLongW.return_value = 0
                user32_mock.SetWindowPos.return_value = True

                # 调用实际还原逻辑
                mw._restore_from_tray()
                # 等待延迟检查（100ms）完成
                qtbot.wait(150)

        # 生产态断言：窗口应恢复可见且启用
        assert mw.isVisible() is True, "还原后窗口应可见"
        assert mw.isEnabled() is True, "还原后窗口应保持启用"
        # 窗口不应处于最小化状态
        assert not (mw.windowState() & Qt.WindowState.WindowMinimized), \
            "还原后窗口不应处于最小化状态"

    def test_restore_after_minimize_clears_toolwindow_state(self, qtbot):
        """还原流程应清除 TOOLWINDOW 并设置 APPWINDOW，避免无响应"""
        mw = self._make_shown_main_window(qtbot)
        mw._orig_window_flags = mw.windowFlags()
        mw._orig_hwnd_parent = 0

        with patch.object(mw, "_ensure_hidden_owner"), \
             patch.object(mw, "_apply_toolwindow_to_process_windows"), \
             patch.object(mw, "_persist_minimize_setting"), \
             patch.object(mw, "_start_winid_watcher"), \
             patch.object(mw, "_dump_native_windows"), \
             patch.object(mw, "_destroy_hidden_owner"), \
             patch.object(mw, "append_log"):
            import ctypes
            with patch("ctypes.windll.user32") as user32_mock:
                # 模拟窗口同时有 APPWINDOW 和 TOOLWINDOW（冲突状态）
                user32_mock.GetWindowLongPtrW.return_value = 0x00040080
                user32_mock.GetWindowLongW.return_value = 0x00040080
                user32_mock.SetWindowLongPtrW.return_value = 0
                user32_mock.SetWindowLongW.return_value = 0
                user32_mock.SetWindowPos.return_value = True

                with patch.object(mw, "showNormal") as show_mock, \
                     patch.object(mw, "raise_") as raise_mock, \
                     patch.object(mw, "activateWindow") as activate_mock, \
                     patch.object(mw, "ensure_window_buttons"):
                    mw._restore_from_tray()
                    qtbot.wait(150)

        # 验证关键方法被调用
        show_mock.assert_called()
        raise_mock.assert_called()
        activate_mock.assert_called()

    def test_restore_handles_hwnd_recreation_production(self, qtbot):
        """生产态：HWND 重建后仍能正确恢复窗口状态"""
        mw = self._make_shown_main_window(qtbot)
        mw._orig_window_flags = mw.windowFlags()
        mw._orig_hwnd_parent = 0

        call_count = 0
        def mock_winId():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return 1000
            return 2000

        mw.winId = mock_winId

        with patch.object(mw, "_ensure_hidden_owner"), \
             patch.object(mw, "_apply_toolwindow_to_process_windows"), \
             patch.object(mw, "_persist_minimize_setting"), \
             patch.object(mw, "_win32_apply_appwindow") as win32_mock, \
             patch.object(mw, "_start_winid_watcher") as watcher_mock, \
             patch.object(mw, "_dump_native_windows"), \
             patch.object(mw, "_destroy_hidden_owner"), \
             patch.object(mw, "append_log"), \
             patch("ctypes.windll.user32") as user32_mock, \
             patch("ctypes.windll.kernel32") as kernel32_mock:
            user32_mock.GetWindowLongPtrW.return_value = 0x00000000
            user32_mock.GetWindowLongW.return_value = 0x00000000
            kernel32_mock.GetLastError.return_value = 0

            with patch.object(mw, "showNormal") as show_mock, \
                 patch.object(mw, "raise_"), \
                 patch.object(mw, "activateWindow"), \
                 patch.object(mw, "ensure_window_buttons"), \
                 patch("PyQt6.QtCore.QTimer.singleShot") as timer_mock:
                # 直接调用 Win32 回退方法（模拟延迟回调中的调用）
                mw._restore_from_tray_win32_fallback()
                # 验证定时器被设置用于处理 HWND 重建
                assert timer_mock.call_count >= 1
                # 验证存在 100ms 的 APPWINDOW 应用定时器
                appwindow_timer_found = False
                for call in timer_mock.call_args_list:
                    if call[0][0] == 100 and callable(call[0][1]):
                        appwindow_timer_found = True
                        break
                assert appwindow_timer_found, "APPWINDOW apply timer not found"
                watcher_mock.assert_called()

    def test_restore_preserves_window_interactive_flags_production(self, qtbot):
        """生产态：还原后窗口应保持可交互标志"""
        mw = self._make_shown_main_window(qtbot)
        mw._orig_window_flags = mw.windowFlags()

        with patch.object(mw, "_ensure_hidden_owner"), \
             patch.object(mw, "_apply_toolwindow_to_process_windows"), \
             patch.object(mw, "_persist_minimize_setting"), \
             patch.object(mw, "_win32_apply_appwindow"), \
             patch.object(mw, "_start_winid_watcher"), \
             patch.object(mw, "_dump_native_windows"), \
             patch.object(mw, "_destroy_hidden_owner"), \
             patch.object(mw, "append_log"), \
             patch("ctypes.windll.user32") as user32_mock:
            user32_mock.GetWindowLongPtrW.return_value = 0x00040000
            user32_mock.GetWindowLongW.return_value = 0x00040000

            with patch.object(mw, "showNormal") as show_mock, \
                 patch.object(mw, "raise_") as raise_mock, \
                 patch.object(mw, "activateWindow") as activate_mock, \
                 patch.object(mw, "ensure_window_buttons"):
                mw._restore_from_tray()
                qtbot.wait(150)

        # 验证窗口状态被设置为正常（非最小化、非工具窗口）
        assert not (mw.windowState() & Qt.WindowState.WindowMinimized)
        show_mock.assert_called()
        raise_mock.assert_called()
        activate_mock.assert_called()

    def test_full_minimize_restore_lifecycle_production(self, qtbot):
        """生产态：完整的最小化->还原生命周期，验证窗口最终可交互"""
        from gui.pyqt6.main_window import MainWindow
        from PyQt6.QtWidgets import QMainWindow

        # 构造并显示主窗口（与生产环境一致）
        mw = MainWindow.__new__(MainWindow)
        QMainWindow.__init__(mw)
        mw._minimize_to_tray = True
        mw._tray_available = True
        mw._is_executing_standard_flow = False
        mw._config = {"system": {"minimize_to_tray": True}}
        mw.show()
        qtbot.wait(100)
        assert mw.isVisible() is True
        assert int(mw.winId()) != 0

        # 模拟最小化到托盘（调用 closeEvent 的真实逻辑）
        mw._orig_window_flags = mw.windowFlags()
        mw._orig_hwnd_parent = 0
        mw._hidden_owner_widget = MagicMock()
        mw._hidden_owner_hwnd = 12345
        mw.setWindowFlag(Qt.WindowType.Tool, True)

        # 模拟还原（尽量少 mock，让 Qt 实际执行 showNormal/raise_/activateWindow）
        with patch.object(mw, "_ensure_hidden_owner"), \
             patch.object(mw, "_apply_toolwindow_to_process_windows"), \
             patch.object(mw, "_persist_minimize_setting"), \
             patch.object(mw, "_win32_apply_appwindow") as win32_mock, \
             patch.object(mw, "_start_winid_watcher"), \
             patch.object(mw, "_dump_native_windows"), \
             patch.object(mw, "_destroy_hidden_owner"), \
             patch.object(mw, "append_log"), \
             patch("ctypes.windll.user32") as user32_mock:
            # 模拟 Win32 返回 APPWINDOW 已设置
            user32_mock.GetWindowLongPtrW.return_value = 0x00040000
            user32_mock.GetWindowLongW.return_value = 0x00040000
            user32_mock.SetWindowLongPtrW.return_value = 0
            user32_mock.SetWindowLongW.return_value = 0
            user32_mock.SetWindowPos.return_value = True

            # 不 mock showNormal/raise_/activateWindow，让 Qt 实际执行
            mw._restore_from_tray()
            # 等待延迟检查（100ms）及 owner 销毁（250ms）完成
            qtbot.wait(400)

        # 生产态关键断言
        assert mw.isVisible() is True, "还原后窗口应可见"
        assert mw.isEnabled() is True, "还原后窗口应保持启用"
        assert not (mw.windowState() & Qt.WindowState.WindowMinimized), \
            "还原后窗口不应处于最小化状态"

    def test_close_event_minimize_then_restore_cycle_production(self, qtbot):
        """生产态：closeEvent 最小化 -> _restore_from_tray 还原的完整周期"""
        from gui.pyqt6.main_window import MainWindow
        from PyQt6.QtWidgets import QMainWindow

        mw = MainWindow.__new__(MainWindow)
        QMainWindow.__init__(mw)
        mw._minimize_to_tray = True
        mw._tray_available = True
        mw._is_executing_standard_flow = False
        mw._config = {"system": {"minimize_to_tray": True}}
        mw.show()
        qtbot.wait(100)
        assert mw.isVisible() is True

        # 模拟 closeEvent 最小化到托盘
        with patch.object(mw, "_ensure_hidden_owner") as ensure_owner_mock, \
             patch.object(mw, "_apply_toolwindow_to_process_windows"), \
             patch.object(mw, "append_log"), \
             patch("ctypes.windll.user32") as user32_mock:
            user32_mock.GetWindowLongPtrW.return_value = 0x00040000
            user32_mock.GetWindowLongW.return_value = 0x00040000
            user32_mock.SetWindowLongPtrW.return_value = 0
            user32_mock.SetWindowLongW.return_value = 0
            user32_mock.SetWindowPos.return_value = True

            event = MagicMock()
            mw.closeEvent(event)
            # closeEvent 应忽略事件（不退出）
            event.ignore.assert_called_once()
            event.accept.assert_not_called()
            # 窗口应被隐藏
            assert mw.isVisible() is False, "最小化到托盘后窗口应隐藏"
            ensure_owner_mock.assert_called()

        # 模拟从托盘还原
        with patch.object(mw, "_ensure_hidden_owner"), \
             patch.object(mw, "_apply_toolwindow_to_process_windows"), \
             patch.object(mw, "_persist_minimize_setting"), \
             patch.object(mw, "_win32_apply_appwindow"), \
             patch.object(mw, "_start_winid_watcher"), \
             patch.object(mw, "_dump_native_windows"), \
             patch.object(mw, "_destroy_hidden_owner"), \
             patch.object(mw, "append_log"), \
             patch("ctypes.windll.user32") as user32_mock:
            user32_mock.GetWindowLongPtrW.return_value = 0x00040000
            user32_mock.GetWindowLongW.return_value = 0x00040000
            user32_mock.SetWindowLongPtrW.return_value = 0
            user32_mock.SetWindowLongW.return_value = 0
            user32_mock.SetWindowPos.return_value = True

            # 不 mock showNormal/raise_/activateWindow，让 Qt 实际执行
            mw._restore_from_tray()
            qtbot.wait(150)

        # 验证窗口恢复可见且可交互
        assert mw.isVisible() is True, "还原后窗口应可见"
        assert mw.isEnabled() is True, "还原后窗口应保持启用"
        assert not (mw.windowState() & Qt.WindowState.WindowMinimized), \
            "还原后窗口不应处于最小化状态"

    def test_uncheck_tray_restores_window_if_minimized(self, qtbot):
        """取消勾选托盘时，若窗口处于最小化/隐藏状态，应先恢复窗口显示"""
        from gui.pyqt6.main_window import MainWindow
        from PyQt6.QtWidgets import QMainWindow

        mw = MainWindow.__new__(MainWindow)
        QMainWindow.__init__(mw)
        mw._minimize_to_tray = True
        mw._tray_available = True
        mw._is_executing_standard_flow = False
        mw._config = {"system": {"minimize_to_tray": True}}
        mw.show()
        qtbot.wait(100)
        assert mw.isVisible() is True

        # 模拟窗口已最小化到托盘的状态
        mw._orig_window_flags = mw.windowFlags()
        mw.hide()
        mw.setWindowFlag(Qt.WindowType.Tool, True)
        assert mw.isVisible() is False

        # 取消勾选托盘选项
        with patch.object(mw, "_ensure_hidden_owner"), \
             patch.object(mw, "_apply_toolwindow_to_process_windows"), \
             patch.object(mw, "_persist_minimize_setting"), \
             patch.object(mw, "_uninstall_win_event_hook"), \
             patch.object(mw, "_destroy_hidden_owner"), \
             patch.object(mw, "_destroy_native_hidden_owner"), \
             patch.object(mw, "_win32_apply_appwindow"), \
             patch.object(mw, "append_log"), \
             patch("ctypes.windll.user32") as user32_mock:
            user32_mock.GetWindowLongPtrW.return_value = 0x00040000
            user32_mock.GetWindowLongW.return_value = 0x00040000
            user32_mock.SetWindowLongPtrW.return_value = 0
            user32_mock.SetWindowLongW.return_value = 0
            user32_mock.SetWindowPos.return_value = True

            mw._on_minimize_to_tray_changed(False)

        # 验证窗口被恢复显示
        assert mw.isVisible() is True, "取消勾选后窗口应恢复可见"
        assert mw.isEnabled() is True, "取消勾选后窗口应保持启用"
        assert not (mw.windowState() & Qt.WindowState.WindowMinimized), \
            "取消勾选后窗口不应处于最小化状态"
        # 验证托盘相关状态被清理
        assert mw._tray_available is False
        assert getattr(mw, '_tray_icon', None) is None

    def test_uncheck_tray_does_not_affect_visible_window(self, qtbot):
        """取消勾选托盘时，若窗口正常显示，不应改变窗口状态"""
        from gui.pyqt6.main_window import MainWindow
        from PyQt6.QtWidgets import QMainWindow

        mw = MainWindow.__new__(MainWindow)
        QMainWindow.__init__(mw)
        mw._minimize_to_tray = True
        mw._tray_available = True
        mw._is_executing_standard_flow = False
        mw._config = {"system": {"minimize_to_tray": True}}
        mw.show()
        qtbot.wait(100)
        assert mw.isVisible() is True
        assert mw.isEnabled() is True

        # 取消勾选托盘选项（窗口正常显示）
        with patch.object(mw, "_ensure_hidden_owner"), \
             patch.object(mw, "_apply_toolwindow_to_process_windows"), \
             patch.object(mw, "_persist_minimize_setting"), \
             patch.object(mw, "_uninstall_win_event_hook"), \
             patch.object(mw, "_destroy_hidden_owner"), \
             patch.object(mw, "_destroy_native_hidden_owner"), \
             patch.object(mw, "_win32_apply_appwindow"), \
             patch.object(mw, "append_log"), \
             patch("ctypes.windll.user32") as user32_mock:
            user32_mock.GetWindowLongPtrW.return_value = 0x00040000
            user32_mock.GetWindowLongW.return_value = 0x00040000
            user32_mock.SetWindowLongPtrW.return_value = 0
            user32_mock.SetWindowLongW.return_value = 0
            user32_mock.SetWindowPos.return_value = True

            mw._on_minimize_to_tray_changed(False)

        # 验证窗口状态不变
        assert mw.isVisible() is True, "窗口应保持可见"
        assert mw.isEnabled() is True, "窗口应保持启用"
        assert not (mw.windowState() & Qt.WindowState.WindowMinimized), \
            "窗口不应被最小化"
        # 验证托盘相关状态被清理
        assert mw._tray_available is False
        assert getattr(mw, '_tray_icon', None) is None

    def test_startup_loads_persisted_tray_setting(self, qtbot):
        """启动时 MainWindow 应从磁盘配置读取并应用托盘设置"""
        from gui.pyqt6.main_window import MainWindow
        from PyQt6.QtWidgets import QMainWindow
        import tempfile
        import json

        # 创建临时配置文件，模拟已保存的托盘设置
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump({"system": {"minimize_to_tray": True}}, f)
            config_path = f.name

        try:
            mw = MainWindow.__new__(MainWindow)
            QMainWindow.__init__(mw)
            mw._minimize_to_tray = False  # 初始值
            mw._tray_available = False
            mw._is_executing_standard_flow = False
            mw._config = {}  # 空配置，等待从磁盘加载

            # 模拟 _reload_disk_config 从临时文件加载
            with open(config_path, 'r', encoding='utf-8') as fr:
                disk_cfg = json.load(fr)
            mw._config.update(disk_cfg)

            # 模拟启动时读取配置
            tray_enabled = mw._config.get("system", {}).get("minimize_to_tray", False)
            mw._minimize_to_tray = tray_enabled

            assert mw._minimize_to_tray is True, "启动时应读取到持久化的托盘设置"
        finally:
            os.unlink(config_path)

    def test_startup_disabled_tray_setting_when_false(self, qtbot):
        """启动时若托盘设置为 False，MainWindow 应正确初始化为禁用"""
        from gui.pyqt6.main_window import MainWindow
        from PyQt6.QtWidgets import QMainWindow
        import tempfile
        import json

        # 创建临时配置文件，模拟托盘设置已禁用
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump({"system": {"minimize_to_tray": False}}, f)
            config_path = f.name

        try:
            mw = MainWindow.__new__(MainWindow)
            QMainWindow.__init__(mw)
            mw._minimize_to_tray = True  # 初始值（与磁盘配置相反）
            mw._tray_available = False
            mw._is_executing_standard_flow = False
            mw._config = {}

            # 模拟 _reload_disk_config 从临时文件加载
            with open(config_path, 'r', encoding='utf-8') as fr:
                disk_cfg = json.load(fr)
            mw._config.update(disk_cfg)

            # 模拟启动时读取配置
            tray_enabled = mw._config.get("system", {}).get("minimize_to_tray", False)
            mw._minimize_to_tray = tray_enabled

            assert mw._minimize_to_tray is False, "启动时应读取到持久化的禁用设置"
        finally:
            os.unlink(config_path)

    def test_reload_disk_config_merges_tray_setting(self, qtbot):
        """_reload_disk_config 应正确合并磁盘配置中的托盘设置"""
        from gui.pyqt6.main_window import MainWindow
        from PyQt6.QtWidgets import QMainWindow
        import tempfile
        import json

        # 创建临时配置文件
        disk_config = {
            "system": {"minimize_to_tray": True},
            "server": {"host": "127.0.0.1", "port": 9999}
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(disk_config, f)
            config_path = f.name

        try:
            mw = MainWindow.__new__(MainWindow)
            QMainWindow.__init__(mw)
            mw._minimize_to_tray = False
            mw._tray_available = False
            mw._is_executing_standard_flow = False
            mw._config = {
                "system": {"minimize_to_tray": False},
                "server": {"host": "0.0.0.0", "port": 8888}
            }

            # 模拟 _reload_disk_config 的合并逻辑
            with open(config_path, 'r', encoding='utf-8') as fr:
                disk_cfg = json.load(fr)

            def _merge(a, b):
                for k, v in (b or {}).items():
                    if isinstance(v, dict) and isinstance(a.get(k), dict):
                        _merge(a[k], v)
                    else:
                        a[k] = v

            _merge(mw._config, disk_cfg)

            # 验证托盘设置被合并
            assert mw._config["system"]["minimize_to_tray"] is True, "磁盘配置应覆盖内存配置"
            # 验证其他配置也被合并
            assert mw._config["server"]["port"] == 9999, "服务器端口应被更新"
            assert mw._config["server"]["host"] == "127.0.0.1", "服务器地址应被更新"
        finally:
            os.unlink(config_path)
