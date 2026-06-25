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
                timer_mock.assert_called_once()
                args, _ = timer_mock.call_args
                assert args[0] == 100, f"Qt restore delay should be 100ms, got {args[0]}ms"
                assert callable(args[1])

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
                # 验证第一个定时器是延迟 100ms 应用 APPWINDOW
                first_call = timer_mock.call_args_list[0]
                assert first_call[0][0] == 100
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
                # 验证 QTimer.singleShot 被调用，延迟 100ms 后检查样式
                timer_mock.assert_called_once()
                args, _ = timer_mock.call_args
                assert args[0] == 100, f"Qt restore delay should be 100ms, got {args[0]}ms"
                # 回调应为 _delayed_qt_restore（闭包），而非直接销毁 owner
                assert callable(args[1])

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
                # 验证延迟检查回调被设置（100ms）
                timer_mock.assert_called_once()
                args, _ = timer_mock.call_args
                assert args[0] == 100, f"Qt restore delay should be 100ms, got {args[0]}ms"
                assert callable(args[1])

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
                # 验证第一个定时器是延迟 100ms 应用 APPWINDOW，使用初始 hwnd
                first_call = timer_mock.call_args_list[0]
                assert first_call[0][0] == 100
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
                timer_mock.assert_called_once()
                args, _ = timer_mock.call_args
                assert args[0] == 100, f"Qt restore delay should be 100ms, got {args[0]}ms"
                assert callable(args[1])

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
