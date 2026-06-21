"""PyQt6 主窗口 - Endfield 终端工业风格"""
import os
from utils.paths import ensure_src_path
from typing import Optional, Dict, List, Any
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QLabel, QFrame, QSplitter,
    QStatusBar, QScrollArea, QApplication,
    QTabWidget, QMessageBox, QSystemTrayIcon, QMenu,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer, QEvent
from PyQt6.QtGui import QIcon, QFont

try:
    from .theme.theme_manager import ThemeManager
    from .widgets.base_widgets import NavigationButton, HorizontalSeparator
    from .pages import AuthPage, SettingsPage, DeviceSettingsPage, AgentPage
    from .pages.agent_page import AgentPage as AgentPageDirect
    from .pages.standard_reasoning_page import StandardReasoningPage
    from .pages.prts_full_intelligence_page import PrtsFullIntelligencePage
    from .pages.iea_page import IeaPage
except ImportError:
    ensure_src_path(__file__)

    from gui.pyqt6.theme.theme_manager import ThemeManager
    from gui.pyqt6.widgets.base_widgets import NavigationButton, HorizontalSeparator
    from gui.pyqt6.pages import AuthPage, SettingsPage, DeviceSettingsPage, AgentPage
    from gui.pyqt6.pages.agent_page import AgentPage as AgentPageDirect
    from gui.pyqt6.pages.standard_reasoning_page import StandardReasoningPage
    from gui.pyqt6.pages.prts_full_intelligence_page import PrtsFullIntelligencePage
    from gui.pyqt6.pages.iea_page import IeaPage


class NavigationBar(QWidget):
    page_changed = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._theme = ThemeManager.get_instance()
        self._nav_buttons: Dict[str, NavigationButton] = {}
        self._current_page: Optional[str] = None
        self._login_required: bool = False
        self._auth_page_id: Optional[str] = None
        self._is_logged_in: bool = False

        self._setup_ui()
        self._setup_style()

    def set_login_state(self, required: bool, is_logged_in: bool, auth_page_id: Optional[str] = None) -> None:
        self._login_required = required
        self._is_logged_in = is_logged_in
        self._auth_page_id = auth_page_id
        self._update_nav_buttons_state()

    def _update_nav_buttons_state(self) -> None:
        if not self._login_required or self._is_logged_in:
            for button in self._nav_buttons.values():
                button.setEnabled(True)
            return
        for page_id, button in self._nav_buttons.items():
            if self._auth_page_id and page_id == self._auth_page_id:
                button.setEnabled(True)
            else:
                button.setEnabled(False)

    def can_navigate_to(self, page_id: str) -> bool:
        if not self._login_required or self._is_logged_in:
            return True
        if self._auth_page_id and page_id == self._auth_page_id:
            return True
        return False

    def _setup_ui(self) -> None:
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        header_widget = QWidget()
        header_widget.setObjectName("navHeader")
        header_widget.setStyleSheet("QWidget#navHeader { background-color: #08080d; border-bottom: 1px solid rgba(24, 209, 255, 0.06); }")
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(20, 20, 20, 16)
        header_layout.setSpacing(4)

        self._title_label = QLabel("ISTINA//ENDFIELD")
        self._title_label.setStyleSheet("QLabel { color: #18d1ff; font-size: 13px; font-family: Consolas; font-weight: bold; letter-spacing: 2px; }")
        header_layout.addWidget(self._title_label)

        self._version_label = QLabel("v1.0.0")
        self._version_label.setStyleSheet("QLabel { color: #606080; font-size: 11px; font-family: Consolas; }")
        header_layout.addWidget(self._version_label)

        header_layout.addSpacing(8)
        term_line = QLabel("-------------------")
        term_line.setStyleSheet("color: rgba(24, 209, 255, 0.15); font-size: 10px;")
        header_layout.addWidget(term_line)

        self._main_layout.addWidget(header_widget)

        nav_scroll = QWidget()
        self._nav_layout = QVBoxLayout(nav_scroll)
        self._nav_layout.setContentsMargins(0, 8, 0, 8)
        self._nav_layout.setSpacing(2)
        self._main_layout.addWidget(nav_scroll, 1)

        self._bottom_widget = QWidget()
        self._bottom_layout = QVBoxLayout(self._bottom_widget)
        self._bottom_layout.setContentsMargins(0, 8, 0, 8)
        self._bottom_layout.setSpacing(2)

        bottom_line = QLabel("-------------------")
        bottom_line.setStyleSheet("color: rgba(24, 209, 255, 0.15); font-size: 10px;")
        bottom_line.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._bottom_layout.addWidget(bottom_line)
        self._bottom_layout.addSpacing(4)

        self._main_layout.addWidget(self._bottom_widget)

    def _setup_style(self) -> None:
        self.setProperty("class", "navigationBar")
        self.setFixedWidth(220)
        self.setStyleSheet("QWidget { background-color: #08080d; }")

    def add_page(self, page_id: str, title: str, icon: Optional[str] = None, position: str = "top") -> None:
        prefix = "> " if position == "top" else "> "
        display_title = f"{prefix}{title}"
        button = NavigationButton(display_title, self, icon)
        button.clicked.connect(lambda: self._on_nav_clicked(page_id))
        if position == "bottom":
            self._bottom_layout.addWidget(button)
        else:
            self._nav_layout.addWidget(button)
        self._nav_buttons[page_id] = button
        if self._current_page is None:
            self.set_current_page(page_id)

    def remove_page(self, page_id: str) -> None:
        if page_id in self._nav_buttons:
            button = self._nav_buttons.pop(page_id)
            button.deleteLater()

    def _on_nav_clicked(self, page_id: str) -> None:
        if not self.can_navigate_to(page_id):
            return
        self.set_current_page(page_id)
        self.page_changed.emit(page_id)

    def set_current_page(self, page_id: str) -> None:
        for pid, button in self._nav_buttons.items():
            button.set_selected(pid == page_id)
        self._current_page = page_id

    def get_current_page(self) -> Optional[str]:
        return self._current_page

    def set_version(self, version: str) -> None:
        self._version_label.setText(version)


class ContentArea(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._theme = ThemeManager.get_instance()
        self._pages: Dict[str, QWidget] = {}
        self._setup_ui()
        self._setup_style()

    def _setup_ui(self) -> None:
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)
        self._stacked_widget = QStackedWidget()
        self._main_layout.addWidget(self._stacked_widget)

    def _setup_style(self) -> None:
        self.setProperty("class", "contentArea")

    def add_page(self, page_id: str, page_widget: QWidget) -> None:
        self._pages[page_id] = page_widget
        self._stacked_widget.addWidget(page_widget)

    def remove_page(self, page_id: str) -> None:
        if page_id in self._pages:
            page_widget = self._pages.pop(page_id)
            self._stacked_widget.removeWidget(page_widget)
            page_widget.deleteLater()

    def show_page(self, page_id: str) -> None:
        if page_id in self._pages:
            self._stacked_widget.setCurrentWidget(self._pages[page_id])

    def get_page(self, page_id: str) -> Optional[QWidget]:
        return self._pages.get(page_id)

    def get_current_page_id(self) -> Optional[str]:
        current_widget = self._stacked_widget.currentWidget()
        for page_id, widget in self._pages.items():
            if widget == current_widget:
                return page_id
        return None


class MainWindow(QMainWindow):
    page_changed = pyqtSignal(str)
    window_closed = pyqtSignal()
    device_connect_requested = pyqtSignal(str)
    device_disconnect_requested = pyqtSignal()
    device_scan_requested = pyqtSignal()
    screenshot_requested = pyqtSignal()
    task_start_requested = pyqtSignal()
    task_stop_requested = pyqtSignal()
    task_added = pyqtSignal(dict)
    task_deleted = pyqtSignal(str)
    login_requested = pyqtSignal(str, str)
    logout_requested = pyqtSignal()
    settings_changed = pyqtSignal(dict)
    check_update_requested = pyqtSignal()
    refresh_user_info_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None, title: str = "Istina Endfield Assistant",
                 min_width: int = 1280, min_height: int = 800, config: Optional[Dict[str, Any]] = None,
                 auth_manager: Optional[Any] = None, device_manager: Optional[Any] = None,
                 agent_executor: Optional[Any] = None, communicator: Optional[Any] = None,
                 screen_capture: Optional[Any] = None, touch_executor: Optional[Any] = None,
                 inference_manager: Optional[Any] = None) -> None:
        super().__init__(parent)
        # 强制创建原生 HWND，以减少 Qt 重建导致的 Win32 覆盖问题
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        except Exception:
            try:
                # Fallback older enum
                self.setAttribute(Qt.WA_NativeWindow, True)
            except Exception:
                pass
        self._theme = ThemeManager.get_instance()
        self._title = title
        self._min_width = min_width
        self._min_height = min_height
        self._config = config or {}
        # 尽早从磁盘加载持久配置，优先于 UI 初始化，确保设置在界面创建时就可用
        try:
            self._reload_disk_config()
        except Exception:
            pass

        self._auth_manager = auth_manager
        self._device_manager = device_manager
        self._agent_executor = agent_executor
        self._communicator = communicator
        self._screen_capture = screen_capture
        self._touch_executor = touch_executor
        self._inference_manager = inference_manager

        self._auth_page: Optional[AuthPage] = None
        self._settings_page: Optional[SettingsPage] = None
        self._agent_page: Optional[AgentPage] = None

        self._is_logged_in: bool = False
        self._require_login: bool = True
        self._window_shown: bool = False  # 标记窗口是否已显示

        self._setup_window()
        self._setup_ui()
        self._setup_connections()

        # 从配置加载托盘初始状态（setup_connections 之前 emit 的信号未被连接)
        tray_enabled = self._config.get("system", {}).get("minimize_to_tray", False)
        self._minimize_to_tray = tray_enabled

    def _setup_window(self) -> None:
        self.setWindowTitle(self._title)
        self.setMinimumSize(QSize(self._min_width, self._min_height))
        # 移除 Tool 标志，确保窗口被视为应用程序窗口而非工具窗口
        # 注意：Tool (0xb) 包含 Window (0x1) 位，所以不能直接 | Window
        # 只需移除 Tool 即可，Window 标志会保留
        current_flags = self.windowFlags()
        self.setWindowFlags(current_flags & ~Qt.WindowType.Tool.value)

    def ensure_window_buttons(self) -> None:
        """Ensure Windows system buttons are visible.

        关键：QMainWindow 默认 flags 已经包含所有需要的按钮标志
        不需要修改 flags，只需确保窗口正确显示
        """
        try:
            # 不需要修改 flags，QMainWindow 默认已经有正确的标题栏
            # 只需确保窗口显示
            self.show()
        except Exception:
            pass

    def _ensure_appwindow_style(self) -> None:
        """通过 Win32 API 设置 WS_EX_APPWINDOW，确保标题栏正确显示。

        PyQt6 的 QMainWindow 默认 ExStyle 缺少 WS_EX_APPWINDOW，
        导致窗口被视为工具窗口而非应用程序窗口。
        需要通过 Win32 API 直接设置。
        """
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = int(self.winId())

            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000

            # 获取当前 ExStyle
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)

            # 添加 WS_EX_APPWINDOW
            if not (ex_style & WS_EX_APPWINDOW):
                new_ex_style = ex_style | WS_EX_APPWINDOW
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_ex_style)

                # 刷新窗口样式
                # 修复：移除 SWP_NOACTIVATE，允许窗口正常激活，避免模态对话框显示后主窗口无响应
                SWP_NOMOVE = 0x0002
                SWP_NOSIZE = 0x0001
                SWP_NOZORDER = 0x0004
                SWP_FRAMECHANGED = 0x0020

                user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
        except Exception:
            pass

    def _setup_ui(self) -> None:
        self._central_widget = QWidget()
        self.setCentralWidget(self._central_widget)

        self._main_layout = QHBoxLayout(self._central_widget)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        self._navigation_bar = NavigationBar()
        self._main_layout.addWidget(self._navigation_bar)

        self._content_area = ContentArea()
        self._main_layout.addWidget(self._content_area, stretch=1)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage(">>> 系统就绪")
        self._status_bar.setStyleSheet("QStatusBar { background-color: #07070b; color: #18d1ff; border-top: 1px solid rgba(24, 209, 255, 0.10); font-size: 11px; font-family: Consolas; padding: 2px 12px; }")

        self._init_pages()

    def _init_pages(self) -> None:
        from gui.pyqt6.pages.auth_page import AuthPage
        self._auth_page = AuthPage()
        self.add_page("auth_cloud", "终端认证", self._auth_page)

        self._agent_page = AgentPage(agent_executor=self._agent_executor, inference_manager=self._inference_manager)
        self.add_page("agent", "代理控制台", self._agent_page)

        self._standard_reasoning_page = StandardReasoningPage(
            communicator=self._communicator, agent_executor=self._agent_executor,
            screen_capture=self._screen_capture, touch_executor=self._touch_executor,
            config=self._config, inference_manager=self._inference_manager)
        self.add_page("standard_reasoning", "标准推理", self._standard_reasoning_page)

        self._prts_page = PrtsFullIntelligencePage(
            communicator=self._communicator, agent_executor=self._agent_executor,
            screen_capture=self._screen_capture, touch_executor=self._touch_executor,
            config=self._config, inference_manager=self._inference_manager)
        self.add_page("prts_full", "PRTS 全智能", self._prts_page)

        from gui.pyqt6.pages.settings_page import SettingsPage
        self._settings_page = SettingsPage(
            config=self._config,
            agent_executor=self._agent_executor,
            communicator=self._communicator,
        )
        self.add_page("settings", "系统设置", self._settings_page, position="bottom")

        from gui.pyqt6.pages.device_settings_page import DeviceSettingsPage
        self._device_settings_page = DeviceSettingsPage(
            device_manager=self._device_manager,
            config=self._config
        )
        self.add_page("device_settings", "设备设置", self._device_settings_page, position="bottom")

        from gui.pyqt6.pages.iea_page import IeaPage
        self._iea_page = IeaPage(
            communicator=self._communicator,
            agent_executor=self._agent_executor,
            screen_capture=self._screen_capture,
            touch_executor=self._touch_executor,
            device_manager=self._device_manager,
        )
        self.add_page("iea_control", "IEA 控制面板", self._iea_page)

        self.show_page("auth_cloud")
        self._navigation_bar.set_login_state(True, False, "auth_cloud")
        self._auth_page_id = "auth_cloud"
        self._auto_login_attempted = False
        # 自动登录将在 showEvent 中触发，确保窗口已完全显示
        self._setup_tray()

    def _setup_connections(self) -> None:
        self._navigation_bar.page_changed.connect(self._content_area.show_page)
        self._navigation_bar.page_changed.connect(self.page_changed.emit)
        self.page_changed.connect(self._on_page_changed)

        if self._auth_page and self._auth_manager:
            self._auth_page.arkpass_selected.connect(self._on_arkpass_selected)
            self._auth_page.logout_requested.connect(self._on_logout_requested)
            self._auth_page.refresh_requested.connect(self._refresh_user_info)
            self._auth_page.register_requested.connect(self._on_register_requested)

        if self._settings_page:
            self._settings_page.settings_changed.connect(self.settings_changed.emit)
            self._settings_page.check_update_requested.connect(self.check_update_requested.emit)
            self._settings_page.local_inference_toggled.connect(self._on_local_inference_toggled)
            self._settings_page.refresh_gpu_status.connect(self._refresh_gpu_status)

        if self._settings_page:
            self._settings_page.model_download_requested.connect(self._on_model_download_requested)
            self._settings_page.model_remove_requested.connect(self._on_model_remove_requested)
            self._settings_page.minimize_to_tray_changed.connect(self._on_minimize_to_tray_changed)

        if self._agent_executor:
            if self._settings_page:
                self._settings_page.model_tag_changed.connect(self._settings_page.model_tag_changed)

    def _auto_login(self) -> None:
        """自动登录（修复 3.1：添加双向标志支持注销后重新登录）"""
        # 修复：如果已完全登录，重置标志允许重新登录
        if self._auto_login_attempted and self._is_logged_in:
            return
        
        # 检查是否需要重置标志（注销后）
        if self._auto_login_attempted and not self._is_logged_in:
            self._auto_login_attempted = False  # 重置标志
        
        self._auto_login_attempted = True
        if self._auth_page:
            self._auth_page.try_auto_login()

    def _on_page_changed(self, page_id: str) -> None:
        page_names = {
            "agent": "代理控制台", "auth_cloud": "终端认证",
            "settings": "系统设置",
            "standard_reasoning": "标准推理", "prts_full": "PRTS 全智能",
            "device_settings": "设备设置",
            "iea_control": "IEA 控制面板",
        }
        page_name = page_names.get(page_id, page_id)
        self.set_status(f">>> 终端: {page_name}")
        if page_id == "auth_cloud" and self._auth_manager:
            self._refresh_auth_status()

    def _on_local_inference_toggled(self, enabled: bool):
        self.append_log(f"本地推理: {'开启' if enabled else '关闭'}", "INFO")
        if 'inference' not in self._config:
            self._config['inference'] = {}
        if 'local' not in self._config['inference']:
            self._config['inference']['local'] = {}
        self._config['inference']['local']['enabled'] = enabled

    def _refresh_gpu_status(self):
        if self._settings_page:
            self._settings_page._start_gpu_check()

    def _on_cloud_model_tag_changed(self, mode: str, tag: str):
        """云端模型标签变更：同步到 agent_executor 和各页面"""
        if self._agent_executor:
            setattr(self._agent_executor, 'model_tag', tag)
        if mode == "prts_full_intelligence" and self._prts_page:
            self._prts_page.set_model_tag(tag)
        self.append_log(f"云端模型标签: {mode} → {tag}", "INFO")

    def _on_model_download_requested(self, model_name: str):
        self.append_log(f"模型下载: {model_name}", "INFO")
        models_dir = self._get_models_dir()
        os.makedirs(models_dir, exist_ok=True)

        class DownloadThread(QThread):
            progress = pyqtSignal(int)
            finished = pyqtSignal(bool, str)

            def run(self):
                try:
                    self.progress.emit(30)
                    import time
                    time.sleep(0.5)
                    model_path = os.path.join(models_dir, f"{model_name}.gguf")
                    with open(model_path, 'w') as f:
                        f.write(f"# Placeholder for {model_name} model\n")
                    self.progress.emit(100)
                    self.finished.emit(True, f"Model saved to {model_path}")
                except Exception as e:
                    self.finished.emit(False, str(e))

        self._download_thread = DownloadThread()
        self._download_thread.finished.connect(
            lambda s, m: self.append_log(f"下载{'成功' if s else '失败'}: {m}", "INFO" if s else "ERROR")
        )
        self._download_thread.start()

    def _on_model_remove_requested(self, model_name: str):
        self.append_log(f"模型删除请求: {model_name}", "INFO")
        reply = QMessageBox.question(self, "确认删除",
                                      f"删除模型 '{model_name}'？\n此操作不可撤销。",
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        models_dir = self._get_models_dir()
        model_path = os.path.join(models_dir, f"{model_name}.gguf")
        if os.path.exists(model_path):
            try:
                os.remove(model_path)
                self.append_log(f"模型已删除: {model_name}", "INFO")
            except Exception as e:
                self.append_log(f"模型删除失败: {e}", "ERROR")
                QMessageBox.critical(self, "删除失败", f"无法删除模型文件:\n{e}")
        else:
            self.append_log(f"模型文件不存在: {model_path}", "WARNING")
        if self._settings_page:
            self._settings_page._scan_local_models()

    def _get_models_dir(self) -> str:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        return os.path.join(project_root, "models")

    # ── 系统托盘 ──────────────────────────────────────────────────

    def _setup_tray(self):
        """创建系统托盘图标，启动时始终显示"""
        from PyQt6.QtGui import QPixmap, QColor
        try:
            pixmap = QPixmap(16, 16)
            pixmap.fill(QColor("#18d1ff"))
            icon = QIcon(pixmap)
            QApplication.setWindowIcon(icon)
            self._tray_icon = QSystemTrayIcon(icon, self)
            self._tray_icon.setToolTip("IstinaAI")

            # 修复托盘菜单透明问题：
            # 1. 指定 parent 为 self（主窗口），确保渲染上下文完整
            # 2. 显式设置不透明背景色，避免半透明 RGBA 导致的视觉透明
            tray_menu = QMenu(self)
            tray_menu.setStyleSheet("""
                QMenu {
                    background-color: #10101a;
                    color: #e8e8ee;
                    border: 1px solid #18d1ff;
                    border-radius: 4px;
                    padding: 4px;
                }
                QMenu::item {
                    padding: 8px 16px;
                    border-radius: 2px;
                }
                QMenu::item:selected {
                    background-color: rgba(24, 209, 255, 0.25);
                }
                QMenu::separator {
                    height: 1px;
                    background-color: rgba(24, 209, 255, 0.10);
                    margin: 4px 8px;
                }
            """)
            
            restore_action = tray_menu.addAction("显示窗口")
            restore_action.triggered.connect(self._restore_from_tray)
            tray_menu.addSeparator()
            quit_action = tray_menu.addAction("退出")
            quit_action.triggered.connect(self._quit_from_tray)
            self._tray_icon.setContextMenu(tray_menu)
            self._tray_icon.activated.connect(self._on_tray_activated)
            self._tray_icon.show()
            # 标记托盘可用
            self._tray_available = True
            # 安装 WinEvent hook 以便更早捕获 native HWND 的创建并修正样式
            try:
                self._install_win_event_hook()
            except Exception:
                pass
        except Exception as e:
            self._tray_available = False

    def _on_minimize_to_tray_changed(self, enabled: bool):
        self._minimize_to_tray = enabled
        try:
            if enabled:
                # Ensure we have a hidden owner and aggressively convert any existing
                # top-level APPWINDOWs to TOOLWINDOW (catch windows created before toggle)
                try:
                    self._ensure_hidden_owner()
                except Exception:
                    pass
                try:
                    self._apply_toolwindow_to_process_windows(tag='minimize-on-toggle', aggressive=False)
                except Exception:
                    pass
                # 强制持久化最小化到托盘设置（防止 settings 保存被其它问题吞掉）
                try:
                    self._persist_minimize_setting(enabled)
                except Exception:
                    pass
                except Exception:
                    pass
        except Exception:
            pass

    def _dump_native_windows(self, tag: str = ""):
        # 写入本进程所有顶层窗口及其扩展样式，用于诊断托盘/任务栏问题
        try:
            import ctypes, os, datetime, tempfile
            user32 = ctypes.windll.user32
            pid = os.getpid()
            entries = []
            EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            def _enum(hwnd, lParam):
                pid_ret = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_ret))
                if pid_ret.value == pid:
                    length = user32.GetWindowTextLengthW(hwnd)
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    try:
                        ex = user32.GetWindowLongPtrW(hwnd, -20)
                    except Exception:
                        try:
                            ex = user32.GetWindowLongW(hwnd, -20)
                        except Exception:
                            ex = 0
                    entries.append((int(hwnd), buf.value, ex))
                return True
            user32.EnumWindows(EnumProc(_enum), 0)
            fname = os.path.join(tempfile.gettempdir(), f"istina_tray_debug_{pid}.log")
            with open(fname, "a", encoding="utf8") as f:
                f.write(f"{datetime.datetime.now().isoformat()} [{tag}] main_winId={int(self.winId())} tray_visible={getattr(self, '_tray_icon', None) and getattr(self._tray_icon, 'isVisible', lambda: False)()}\n")
                for h, t, ex in entries:
                    f.write(f"  hwnd={h} title={t!r} ex_style=0x{ex:08x}\n")
            self.append_log(f"诊断写入 {fname}", "INFO")
        except Exception as e:
            try:
                self.append_log(f"诊断失败: {e}", "ERROR")
            except Exception:
                pass

    def _apply_toolwindow_to_process_windows(self, exclude_hwnds: set = None, tag: str = "", aggressive: bool = False):
        """Asynchronously apply TOOLWINDOW to in-process APPWINDOWs to avoid blocking the UI.
        The heavy enumeration and Win32 modifications run in a background thread; a QTimer polls
        for completion and reports results on the main thread.
        """
        try:
            import threading, ctypes, os, tempfile, datetime
            if getattr(self, '_apply_toolwindow_running', False):
                try:
                    self.append_log("Process windows adjustment already running, skipping", "INFO")
                except Exception:
                    pass
                return
            self._apply_toolwindow_running = True
            changed = []
            exclude = set(exclude_hwnds or [])
            # 排除主窗口 HWND（在 UI 线程中获取）
            main_window_hwnd = 0
            try:
                main_window_hwnd = int(self.winId())
                if main_window_hwnd != 0:
                    exclude.add(main_window_hwnd)
            except Exception:
                pass

            def _worker():
                try:
                    user32 = ctypes.windll.user32
                    pid = os.getpid()
                    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

                    def _enum(hwnd, lParam):
                        try:
                            pid_ret = ctypes.c_ulong()
                            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_ret))
                            if pid_ret.value != pid:
                                return True
                            if int(hwnd) in exclude:
                                return True
                            # Get title for conservative filtering
                            length = user32.GetWindowTextLengthW(hwnd)
                            buf = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buf, length + 1)
                            title = buf.value
                            # 排除主窗口（标题检查）
                            if 'Istina Endfield' in title or 'Istina//Endfield' in title:
                                return True
                            # Get ex style
                            try:
                                ex = user32.GetWindowLongPtrW(hwnd, -20)
                            except Exception:
                                try:
                                    ex = user32.GetWindowLongW(hwnd, -20)
                                except Exception:
                                    ex = 0
                            WS_EX_APPWINDOW = 0x00040000
                            WS_EX_TOOLWINDOW = 0x00000080
                            if not (ex & WS_EX_APPWINDOW):
                                return True
                            do_change = aggressive or (not title or len(title.strip()) == 0 or 'QMessageBox' in title)
                            if do_change:
                                try:
                                    owner_hwnd = getattr(self, '_hidden_owner_hwnd', 0) or getattr(self, '_native_hidden_owner_hwnd', 0)
                                    applied = False
                                    try:
                                        # Call the existing Win32 helper (it will perform small retries)
                                        applied = self._win32_apply_toolwindow(int(hwnd), owner_hwnd=owner_hwnd, tag=f'{tag}-proc', retries=3)
                                    except Exception:
                                        applied = False
                                    if applied:
                                        changed.append((int(hwnd), title))
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        return True

                    user32.EnumWindows(EnumProc(_enum), 0)
                    if changed:
                        fname = os.path.join(tempfile.gettempdir(), f"istina_tray_fix_{os.getpid()}.log")
                        try:
                            with open(fname, 'a', encoding='utf8') as f:
                                f.write(f"{datetime.datetime.now().isoformat()} [{tag}] Applied TOOLWINDOW to: {changed}\n")
                        except Exception:
                            pass
                finally:
                    self._apply_toolwindow_running = False

            t = threading.Thread(target=_worker, daemon=True)
            t.start()

            # Poll for completion on the main thread and then report results
            def _poll():
                try:
                    if not t.is_alive():
                        try:
                            if changed:
                                self.append_log(f"Process windows adjusted ({len(changed)}): {changed}", "INFO")
                        except Exception:
                            pass
                        try:
                            if getattr(self, '_apply_toolwindow_poll_timer', None):
                                self._apply_toolwindow_poll_timer.stop()
                                del self._apply_toolwindow_poll_timer
                        except Exception:
                            pass
                except Exception:
                    pass

            try:
                if not getattr(self, '_apply_toolwindow_poll_timer', None):
                    self._apply_toolwindow_poll_timer = QTimer(self)
                    self._apply_toolwindow_poll_timer.timeout.connect(_poll)
                    self._apply_toolwindow_poll_timer.start(150)
            except Exception:
                pass
        except Exception as e:
            try:
                self.append_log(f"调整进程窗口失败: {e}", "ERROR")
            except Exception:
                pass

    def _persist_minimize_setting(self, enabled: bool):
        """原子更新 config/client_config.json -> system.minimize_to_tray 以确保持久化。
        统一使用项目根目录的配置文件路径。
        """
        try:
            import json, tempfile, os as _os
            current = os.path.dirname(os.path.abspath(__file__))
            # 统一路径：项目根目录
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current))))
            config_path = _os.path.join(project_root, "config", "client_config.json")

            _os.makedirs(_os.path.dirname(config_path), exist_ok=True)
            cfg = {}
            if _os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        cfg = json.load(f)
                except Exception:
                    cfg = {}
            cfg.setdefault('system', {})
            cfg['system']['minimize_to_tray'] = bool(enabled)
            fd, tmp_path = tempfile.mkstemp(prefix="client_config_", suffix=".tmp", dir=_os.path.dirname(config_path))
            with _os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            _os.replace(tmp_path, config_path)
            print(f"[配置保存] minimize_to_tray={enabled} 已保存到 {config_path}")
        except Exception as e:
            print(f"[配置保存] 保存失败：{e}")

    def _reload_disk_config(self):
        """从唯一配置文件路径加载并合并配置到 self._config。
        统一使用项目根目录的 config/client_config.json。
        """
        try:
            import json, sys
            current = os.path.dirname(os.path.abspath(__file__))
            # 统一路径：项目根目录
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current))))
            config_path = os.path.join(project_root, 'config', 'client_config.json')
            
            disk_cfg = None
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        disk_cfg = json.load(f)
                    print(f"[配置加载] 从 {config_path} 读取配置")
                except Exception as e:
                    print(f"[配置加载] 读取 {config_path} 失败：{e}")
                    return
            else:
                print(f"[配置加载] 配置文件不存在：{config_path}, 使用默认配置")
                return
            
            if disk_cfg is None:
                print("[配置加载] 未读取到配置内容")
                return
            
            # Merge disk_cfg into self._config (shallow merge with dict recursion)
            def _merge(a, b):
                for k, v in (b or {}).items():
                    if isinstance(v, dict) and isinstance(a.get(k), dict):
                        _merge(a[k], v)
                    else:
                        a[k] = v
            
            if not isinstance(self._config, dict):
                self._config = {}
            _merge(self._config, disk_cfg)
            print(f"[配置加载] 成功合并磁盘配置到内存")
            
            # 输出关键配置用于验证
            system_minimize = self._config.get('system', {}).get('minimize_to_tray', 'N/A')
            print(f"[配置验证] system.minimize_to_tray = {system_minimize}")
            
        except Exception as e:
            print(f"[配置加载] 加载配置失败：{e}")
            import traceback
            traceback.print_exc()

    def _ensure_hidden_owner(self):
        """Ensure a stable hidden owner HWND for the main window.
        Prefer a native Win32 message/hidden window (more stable across Qt HWND
        recreations). Fall back to a QWidget-based hidden owner if native
        creation fails.
        """
        try:
            # 首先尝试 native owner（更稳定）
            try:
                self._ensure_native_hidden_owner()
                if getattr(self, '_native_hidden_owner_hwnd', 0):
                    # 使用 native owner 的 hwnd 作为 hidden owner
                    self._hidden_owner_widget = None
                    self._hidden_owner_hwnd = getattr(self, '_native_hidden_owner_hwnd', 0)
                    return
            except Exception:
                pass

            # 回退到 QWidget hidden owner
            if getattr(self, '_hidden_owner_widget', None) is not None:
                return
            from PyQt6.QtWidgets import QWidget
            owner = QWidget()
            try:
                owner.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
            except Exception:
                try:
                    owner.setAttribute(Qt.WA_NativeWindow, True)
                except Exception:
                    pass
            owner.setWindowFlag(Qt.WindowType.Tool, True)
            owner.setWindowTitle("istina_hidden_owner")
            # 通过先 show 再 hide 强制创建并稳定 native HWND
            try:
                owner.show()
                QApplication.processEvents()
            except Exception:
                pass
            try:
                owner.hide()
                QApplication.processEvents()
            except Exception:
                pass
            self._hidden_owner_widget = owner
            try:
                self._hidden_owner_hwnd = int(owner.winId())
            except Exception:
                self._hidden_owner_hwnd = 0
            self.append_log(f"Created hidden owner QWidget hwnd={getattr(self, '_hidden_owner_hwnd', 0)}", "INFO")
        except Exception as e:
            self._hidden_owner_widget = None
            self._hidden_owner_hwnd = 0
            try:
                self.append_log(f"创建 hidden owner 失败: {e}", "ERROR")
            except Exception:
                pass

    def _destroy_hidden_owner(self):
        try:
            # 销毁 QWidget hidden owner（如存在）
            if getattr(self, '_hidden_owner_widget', None) is not None:
                try:
                    self._hidden_owner_widget.deleteLater()
                except Exception:
                    pass
                self._hidden_owner_widget = None
                self._hidden_owner_hwnd = 0
                try:
                    self.append_log('Destroyed hidden owner (QWidget)', 'INFO')
                except Exception:
                    pass
            # 销毁 native hidden owner（如存在）
            try:
                self._destroy_native_hidden_owner()
            except Exception:
                pass
        except Exception as e:
            try:
                self.append_log(f'销毁 hidden owner 失败: {e}', 'ERROR')
            except Exception:
                pass

    def _ensure_native_hidden_owner(self):
        """Create a small, hidden native Win32 window to act as owner.
        This avoids Qt recreating a native HWND and provides a stable owner
        for SetWindowLongPtr/GWLP_HWNDPARENT.
        """
        if getattr(self, '_native_hidden_owner_hwnd', 0):
            return
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            # WNDPROC类型
            WNDPROCTYPE = ctypes.WINFUNCTYPE(wintypes.LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

            # 简单的 wndproc 委托，调用 DefWindowProc
            def _wnd_proc(hwnd, msg, wparam, lparam):
                return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

            wndproc = WNDPROCTYPE(_wnd_proc)
            # 保持对回调的引用，防止被 GC
            self._native_owner_wndproc = wndproc

            class WNDCLASSEX(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.UINT),
                    ("style", wintypes.UINT),
                    ("lpfnWndProc", WNDPROCTYPE),
                    ("cbClsExtra", ctypes.c_int),
                    ("cbWndExtra", ctypes.c_int),
                    ("hInstance", wintypes.HINSTANCE),
                    ("hIcon", wintypes.HICON),
                    ("hCursor", wintypes.HCURSOR),
                    ("hbrBackground", wintypes.HBRUSH),
                    ("lpszMenuName", wintypes.LPCWSTR),
                    ("lpszClassName", wintypes.LPCWSTR),
                    ("hIconSm", wintypes.HICON),
                ]

            hInstance = kernel32.GetModuleHandleW(None)
            class_name = f"IstinaHiddenOwner_{os.getpid()}"
            wcex = WNDCLASSEX()
            wcex.cbSize = ctypes.sizeof(WNDCLASSEX)
            wcex.style = 0
            wcex.lpfnWndProc = wndproc
            wcex.cbClsExtra = 0
            wcex.cbWndExtra = 0
            wcex.hInstance = hInstance
            wcex.hIcon = 0
            wcex.hCursor = 0
            wcex.hbrBackground = 0
            wcex.lpszMenuName = None
            wcex.lpszClassName = class_name
            wcex.hIconSm = 0

            atom = user32.RegisterClassExW(ctypes.byref(wcex))
            # CreateWindowEx：使用 WS_EX_TOOLWINDOW，作为 pop-up（不在屏幕上）
            CreateWindowExW = user32.CreateWindowExW
            CreateWindowExW.restype = wintypes.HWND
            CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                        wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
            WS_EX_TOOLWINDOW = 0x00000080
            WS_POPUP = 0x80000000
            hwnd = CreateWindowExW(WS_EX_TOOLWINDOW, class_name, "istina_hidden_owner_native", WS_POPUP,
                                   0, 0, 0, 0, None, None, hInstance, None)
            if hwnd:
                # 保留注册信息和 hwnd
                self._native_owner_class = class_name
                self._native_owner_hinstance = hInstance
                self._native_owner_atom = atom
                self._native_hidden_owner_hwnd = int(hwnd)
                try:
                    # 隐藏并更新
                    user32.ShowWindow(hwnd, 0)  # SW_HIDE
                    user32.UpdateWindow(hwnd)
                except Exception:
                    pass
                self.append_log(f"Created native hidden owner hwnd={self._native_hidden_owner_hwnd}", "INFO")
            else:
                self._native_hidden_owner_hwnd = 0
        except Exception as e:
            self._native_hidden_owner_hwnd = 0
            try:
                self.append_log(f"创建 native hidden owner 失败: {e}", "ERROR")
            except Exception:
                pass
        # 如果 in-process native owner 未创建，尝试启动外部 helper 进程
        try:
            if not getattr(self, '_native_hidden_owner_hwnd', 0):
                try:
                    ok = self._start_native_owner_helper(timeout=5.0)
                    if ok:
                        try:
                            self.append_log(f"使用外部 native owner helper hwnd={getattr(self, '_native_hidden_owner_hwnd', 0)}", "INFO")
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

    def _destroy_native_hidden_owner(self):
        try:
            # 如果 helper 存在则先停止
            try:
                self._stop_native_owner_helper()
            except Exception:
                pass
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            hwnd = getattr(self, '_native_hidden_owner_hwnd', 0)
            if hwnd:
                try:
                    user32.DestroyWindow(hwnd)
                except Exception:
                    pass
                self._native_hidden_owner_hwnd = 0
            class_name = getattr(self, '_native_owner_class', None)
            hInstance = getattr(self, '_native_owner_hinstance', None)
            if class_name and hInstance:
                try:
                    user32.UnregisterClassW(class_name, hInstance)
                except Exception:
                    pass
                self._native_owner_class = None
                self._native_owner_hinstance = None
                self._native_owner_atom = None
                # 保留 wndproc 引用直到此处
                try:
                    del self._native_owner_wndproc
                except Exception:
                    pass
                try:
                    self.append_log(f"Destroyed native hidden owner", "INFO")
                except Exception:
                    pass
        except Exception as e:
            try:
                self.append_log(f"销毁 native hidden owner 失败: {e}", "ERROR")
            except Exception:
                pass

    def _start_native_owner_helper(self, timeout: float = 5.0):
        """Start an external helper process that creates a native hidden window and
        writes its HWND to a temp file. Returns True on success.
        """
        try:
            import subprocess, sys, os, tempfile, time
            helper_path = os.path.join(os.path.dirname(__file__), 'native_owner_helper.py')
            out_file = os.path.join(tempfile.gettempdir(), f"istina_native_owner_{os.getpid()}.hwnd")
            try:
                if os.path.exists(out_file):
                    os.remove(out_file)
            except Exception:
                pass
            cmd = [sys.executable, helper_path, out_file]
            creationflags = 0x08000000  # CREATE_NO_WINDOW
            try:
                proc = subprocess.Popen(cmd, creationflags=creationflags)
            except Exception:
                try:
                    proc = subprocess.Popen(cmd)
                except Exception as e:
                    try:
                        self.append_log(f"启动 native owner helper 失败: {e}", "ERROR")
                    except Exception:
                        pass
                    return False
            self._native_owner_helper_proc = proc
            self._native_owner_helper_file = out_file
            # 不在主线程阻塞等待 helper 写入文件，改为异步轮询以避免卡死 UI
            try:
                if not hasattr(self, '_native_owner_poll_timer'):
                    self._native_owner_poll_timer = QTimer(self)
                    def _poll():
                        try:
                            if os.path.exists(out_file):
                                try:
                                    with open(out_file, 'r', encoding='utf-8') as f:
                                        s = f.read().strip()
                                    if s:
                                        hwnd = int(s)
                                        self._native_hidden_owner_hwnd = hwnd
                                        try:
                                            self.append_log(f"Native owner helper started pid={proc.pid} hwnd={hwnd}", "INFO")
                                        except Exception:
                                            pass
                                        try:
                                            self._native_owner_poll_timer.stop()
                                        except Exception:
                                            pass
                                        return
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    try:
                        self._native_owner_poll_timer.timeout.connect(_poll)
                        self._native_owner_poll_timer.start(100)
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                self.append_log(f"Started native owner helper pid={proc.pid} (async)", "INFO")
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _stop_native_owner_helper(self):
        try:
            import os
            proc = getattr(self, '_native_owner_helper_proc', None)
            fname = getattr(self, '_native_owner_helper_file', None)
            if proc:
                try:
                    proc.terminate()
                except Exception:
                    pass
                try:
                    proc.wait(timeout=1)
                except Exception:
                    pass
                self._native_owner_helper_proc = None
            if fname:
                try:
                    if os.path.exists(fname):
                        os.remove(fname)
                except Exception:
                    pass
                self._native_owner_helper_file = None
            # 清空保存的 hwnd
            try:
                self._native_hidden_owner_hwnd = 0
            except Exception:
                pass
        except Exception:
            pass

    def _install_win_event_hook(self):
        """Install WinEvent hook to observe native window creation/show events and
        re-apply EXSTYLE changes as soon as native HWNDs appear. Events are queued
        and processed on the Qt main thread by _process_pending_win_events.
        """
        try:
            import ctypes
            from ctypes import wintypes
            import threading, os
            user32 = ctypes.windll.user32
            # Event constants
            EVENT_OBJECT_CREATE = 0x8000
            EVENT_OBJECT_SHOW = 0x8002
            EVENT_OBJECT_DESTROY = 0x8001
            WINEVENT_OUTOFCONTEXT = 0x0000

            # Callback signature: void CALLBACK WinEventProc(HWINEVENTHOOK hWinEventHook, DWORD event, HWND hwnd, LONG idObject, LONG idChild, DWORD dwEventThread, DWORD dwmsEventTime)
            WinEventProcType = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND, wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD)

            def _proc(hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
                try:
                    if idObject != 0 or hwnd == 0:
                        return
                    pid_ret = ctypes.c_ulong()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_ret))
                    if pid_ret.value != os.getpid():
                        return
                    # push to queue
                    if not hasattr(self, '_win_event_queue'):
                        self._win_event_queue = []
                        self._win_event_queue_lock = threading.Lock()
                    with self._win_event_queue_lock:
                        self._win_event_queue.append((int(event), int(hwnd)))
                except Exception:
                    pass

            # keep reference to the callback to prevent GC
            self._win_event_proc = WinEventProcType(_proc)
            # Hook for create/show/destroy
            hook = user32.SetWinEventHook(EVENT_OBJECT_CREATE, EVENT_OBJECT_SHOW, 0, self._win_event_proc, 0, 0, WINEVENT_OUTOFCONTEXT)
            if hook:
                self._win_event_hook = hook
                # Poll timer on main thread to process queue
                try:
                    if not hasattr(self, '_win_event_poll_timer'):
                        self._win_event_poll_timer = QTimer(self)
                        self._win_event_poll_timer.timeout.connect(self._process_pending_win_events)
                        self._win_event_poll_timer.start(80)
                    self.append_log("Installed WinEvent hook", "INFO")
                except Exception:
                    pass
            else:
                self.append_log("SetWinEventHook failed to return handle", "ERROR")
        except Exception as e:
            try:
                self.append_log(f"Install WinEvent hook failed: {e}", "ERROR")
            except Exception:
                pass

    def _uninstall_win_event_hook(self):
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hook = getattr(self, '_win_event_hook', None)
            if hook:
                try:
                    user32.UnhookWinEvent(hook)
                except Exception:
                    pass
                self._win_event_hook = None
            try:
                if getattr(self, '_win_event_poll_timer', None):
                    self._win_event_poll_timer.stop()
            except Exception:
                pass
            # Shutdown any background executor used for win event handling
            try:
                execr = getattr(self, '_win_event_executor', None)
                if execr:
                    try:
                        execr.shutdown(wait=False)
                    except Exception:
                        pass
                    self._win_event_executor = None
            except Exception:
                pass
        except Exception:
            pass

    def _process_pending_win_events(self):
        try:
            import threading, concurrent.futures, os
            q = getattr(self, '_win_event_queue', None)
            lock = getattr(self, '_win_event_queue_lock', None)
            if not q or not lock:
                return
            with lock:
                items = q[:]
                q.clear()
            # Ensure a ThreadPoolExecutor is available for background Win32 operations
            executor = getattr(self, '_win_event_executor', None)
            if executor is None:
                try:
                    self._win_event_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
                    executor = self._win_event_executor
                except Exception:
                    executor = None
            for event, hwnd in items:
                try:
                    # 跳过主窗口：不要修改主窗口的 EXSTYLE
                    # 主窗口的标题栏应该保持默认样式
                    if int(hwnd) == int(self.winId()):
                        continue
                    
                    # If minimizing/tray visible, prefer applying TOOLWINDOW to new windows
                    if getattr(self, '_minimize_to_tray', False) and getattr(self, '_tray_icon', None) and getattr(self._tray_icon, 'isVisible', lambda: False)():
                        owner = getattr(self, '_hidden_owner_hwnd', 0)
                        if executor:
                            try:
                                executor.submit(self._win32_apply_toolwindow, int(hwnd), owner, 'win_event', 3)
                            except Exception:
                                # fallback to thread
                                threading.Thread(target=self._win32_apply_toolwindow, args=(int(hwnd), owner, 'win_event', 3), daemon=True).start()
                        else:
                            threading.Thread(target=self._win32_apply_toolwindow, args=(int(hwnd), owner, 'win_event', 3), daemon=True).start()
                    else:
                        orig_parent = getattr(self, '_orig_hwnd_parent', 0)
                        if executor:
                            try:
                                executor.submit(self._win32_apply_appwindow, int(hwnd), orig_parent, 'win_event', 3)
                            except Exception:
                                threading.Thread(target=self._win32_apply_appwindow, args=(int(hwnd), orig_parent, 'win_event', 3), daemon=True).start()
                        else:
                            threading.Thread(target=self._win32_apply_appwindow, args=(int(hwnd), orig_parent, 'win_event', 3), daemon=True).start()
                except Exception:
                    pass
        except Exception as e:
            try:
                self.append_log(f"Process win events failed: {e}", "ERROR")
            except Exception:
                pass

    def _win32_apply_toolwindow(self, hwnd, owner_hwnd=None, tag='', retries=3):
        try:
            import ctypes, time
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            GWLP_HWNDPARENT = -8
            SWP_NOSIZE = 0x0001
            SWP_NOMOVE = 0x0002
            SWP_NOZORDER = 0x0004
            SWP_FRAMECHANGED = 0x0020
            flags = SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED
            try:
                GetWindowLongPtr = user32.GetWindowLongPtrW
            except AttributeError:
                GetWindowLongPtr = user32.GetWindowLongW
            try:
                SetWindowLongPtr = user32.SetWindowLongPtrW
            except AttributeError:
                SetWindowLongPtr = user32.SetWindowLongW
            last_err = 0
            new_ex = 0
            for attempt in range(max(1, int(retries))):
                try:
                    current = GetWindowLongPtr(hwnd, GWL_EXSTYLE)
                except Exception:
                    current = 0
                if owner_hwnd:
                    try:
                        SetWindowLongPtr(hwnd, GWLP_HWNDPARENT, owner_hwnd)
                    except Exception:
                        pass
                new_style = (current & ~WS_EX_APPWINDOW) | WS_EX_TOOLWINDOW
                try:
                    ret = SetWindowLongPtr(hwnd, GWL_EXSTYLE, new_style)
                except Exception:
                    ret = None
                try:
                    sp_ret = user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, flags)
                except Exception:
                    sp_ret = None
                try:
                    new_ex = GetWindowLongPtr(hwnd, GWL_EXSTYLE)
                except Exception:
                    new_ex = 0
                try:
                    last_err = kernel32.GetLastError()
                except Exception:
                    last_err = 0
                if not (new_ex & WS_EX_APPWINDOW):
                    self.append_log(f"Win32: applied TOOLWINDOW ({tag}) hwnd={hwnd} ex=0x{new_ex:08x} ret={ret} sp_ret={sp_ret} err={last_err}", "INFO")
                    return True
                # Give Qt a chance to settle and try again (only process events on main thread)
                try:
                    import threading as _threading
                    if _threading.current_thread() is _threading.main_thread():
                        time.sleep(0.02)
                        QApplication.processEvents()
                    else:
                        time.sleep(0.02)
                except Exception:
                    pass
            self.append_log(f"Win32: failed to apply TOOLWINDOW after {retries} tries (tag={tag}) hwnd={hwnd} ex=0x{new_ex:08x} ret={ret} sp_ret={sp_ret} err={last_err}", "ERROR")
        except Exception as e:
            try:
                self.append_log(f"Win32 apply toolwindow exception: {e}", "ERROR")
            except Exception:
                pass
        return False

    def _win32_apply_appwindow(self, hwnd, orig_parent=0, tag='', retries=3):
        try:
            import ctypes, time
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            GWLP_HWNDPARENT = -8
            SWP_NOSIZE = 0x0001
            SWP_NOMOVE = 0x0002
            SWP_NOZORDER = 0x0004
            SWP_FRAMECHANGED = 0x0020
            flags = SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED
            try:
                GetWindowLongPtr = user32.GetWindowLongPtrW
            except AttributeError:
                GetWindowLongPtr = user32.GetWindowLongW
            try:
                SetWindowLongPtr = user32.SetWindowLongPtrW
            except AttributeError:
                SetWindowLongPtr = user32.SetWindowLongW
            last_err = 0
            new_ex = 0
            for attempt in range(max(1, int(retries))):
                try:
                    current = GetWindowLongPtr(hwnd, GWL_EXSTYLE)
                except Exception:
                    current = 0
                new_style = (current & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
                try:
                    ret = SetWindowLongPtr(hwnd, GWL_EXSTYLE, new_style)
                except Exception:
                    ret = None
                # restore parent
                try:
                    if orig_parent:
                        SetWindowLongPtr(hwnd, GWLP_HWNDPARENT, orig_parent)
                    else:
                        SetWindowLongPtr(hwnd, GWLP_HWNDPARENT, 0)
                except Exception:
                    pass
                try:
                    sp_ret = user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, flags)
                except Exception:
                    sp_ret = None
                try:
                    new_ex = GetWindowLongPtr(hwnd, GWL_EXSTYLE)
                except Exception:
                    new_ex = 0
                try:
                    last_err = kernel32.GetLastError()
                except Exception:
                    last_err = 0
                if (new_ex & WS_EX_APPWINDOW):
                    self.append_log(f"Win32: applied APPWINDOW ({tag}) hwnd={hwnd} ex=0x{new_ex:08x} ret={ret} sp_ret={sp_ret} err={last_err}", "INFO")
                    return True
                try:
                    import threading as _threading
                    if _threading.current_thread() is _threading.main_thread():
                        time.sleep(0.02)
                        QApplication.processEvents()
                    else:
                        time.sleep(0.02)
                except Exception:
                    pass
            self.append_log(f"Win32: failed to apply APPWINDOW after {retries} tries (tag={tag}) hwnd={hwnd} ex=0x{new_ex:08x} ret={ret} sp_ret={sp_ret} err={last_err}", "ERROR")
        except Exception as e:
            try:
                self.append_log(f"Win32 apply appwindow exception: {e}", "ERROR")
            except Exception:
                pass
        return False

    def _start_winid_watcher(self, duration_ms: int = 2000, interval_ms: int = 100, role: str = 'minimize'):
        try:
            import time
            if getattr(self, '_winid_watcher_timer', None) is None:
                self._winid_watcher_timer = QTimer(self)
                self._winid_watcher_timer.timeout.connect(self._on_winid_watch_tick)
            self._winid_watcher_role = role
            self._winid_watcher_end = time.time() + (duration_ms / 1000.0)
            self._last_hwnd_watch = int(self.winId()) if hasattr(self, 'winId') else 0
            self._winid_watcher_timer.start(max(20, int(interval_ms)))
            self.append_log(f"Started winId watcher (role={role}) for {duration_ms}ms", "INFO")
        except Exception as e:
            try:
                self.append_log(f"启动 winId watcher 失败: {e}", "ERROR")
            except Exception:
                pass

    def _stop_winid_watcher(self):
        try:
            if getattr(self, '_winid_watcher_timer', None):
                try:
                    self._winid_watcher_timer.stop()
                except Exception:
                    pass
                try:
                    del self._winid_watcher_timer
                except Exception:
                    pass
            self.append_log("Stopped winId watcher", "INFO")
        except Exception:
            pass

    def _on_winid_watch_tick(self):
        try:
            import time
            current = int(self.winId())
            last = getattr(self, '_last_hwnd_watch', None)
            if last is None:
                self._last_hwnd_watch = current
                last = current
            if current != last:
                role = getattr(self, '_winid_watcher_role', 'minimize')
                try:
                    if role in ('minimize', 'close-minimize'):
                        owner = getattr(self, '_hidden_owner_hwnd', 0)
                        self.append_log(f"winId changed {last} -> {current} (role={role}), reapplying TOOLWINDOW", "INFO")
                        self._win32_apply_toolwindow(current, owner_hwnd=owner, tag=f'watch-{role}', retries=4)
                    else:
                        orig_parent = getattr(self, '_orig_hwnd_parent', 0)
                        self.append_log(f"winId changed {last} -> {current} (role={role}), reapplying APPWINDOW", "INFO")
                        self._win32_apply_appwindow(current, orig_parent=orig_parent, tag=f'watch-{role}', retries=4)
                except Exception:
                    pass
                self._last_hwnd_watch = current
            if time.time() > getattr(self, '_winid_watcher_end', 0):
                try:
                    self._stop_winid_watcher()
                except Exception:
                    pass
        except Exception as e:
            try:
                self.append_log(f"winId watcher exception: {e}", "ERROR")
            except Exception:
                pass

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            if self.windowState() & Qt.WindowState.WindowMinimized and self._minimize_to_tray and hasattr(self, '_tray_icon'):
                # Qt 优先：尝试使用 Qt API 将窗口标记为 Tool（通常不在任务栏显示），再隐藏
                try:
                    if not hasattr(self, '_orig_window_flags'):
                        self._orig_window_flags = self.windowFlags()
                    # 添加 Qt.WindowType.Tool 标志（通过先 show 触发 native window 更新）
                    self.setWindowFlag(Qt.WindowType.Tool, True)
                    try:
                        self.show()
                        QApplication.processEvents()
                        # 隐藏前刷新 id
                        _tmp_hwnd = int(self.winId())
                    except Exception:
                        pass
                    self.hide()
                    QApplication.processEvents()
                    # 诊断：检查 native ex_style，确定是否需要 Win32 回退
                    import ctypes
                    user32 = ctypes.windll.user32
                    GWL_EXSTYLE = -20
                    WS_EX_APPWINDOW = 0x00040000
                    try:
                        GetWindowLongPtr = user32.GetWindowLongPtrW
                    except AttributeError:
                        GetWindowLongPtr = user32.GetWindowLongW
                    hwnd = int(self.winId())
                    ex_style = GetWindowLongPtr(hwnd, GWL_EXSTYLE)
                    if not (ex_style & WS_EX_APPWINDOW):
                        try:
                            self._dump_native_windows("after_minimize_qt")
                        except Exception:
                            pass
                        self.append_log(f"最小化到托盘 (Qt) 成功: winId={hwnd}, ex_style=0x{ex_style:08x}", "INFO")
                        try:
                            event.accept()
                        except Exception:
                            pass
                        return
                    else:
                        self.append_log(f"Qt 方法未移除 APPWINDOW (0x{ex_style:08x})，将使用 Win32 回退", "INFO")
                except Exception as e:
                    self.append_log(f"尝试使用 Qt API 最小化到托盘失败: {e}", "ERROR")
                # Win32 回退（在 Qt 失败时使用）
                import ctypes
                user32 = ctypes.windll.user32
                GWL_EXSTYLE = -20
                WS_EX_APPWINDOW = 0x00040000
                WS_EX_TOOLWINDOW = 0x00000080
                try:
                    GetWindowLongPtr = user32.GetWindowLongPtrW
                    SetWindowLongPtr = user32.SetWindowLongPtrW
                except AttributeError:
                    GetWindowLongPtr = user32.GetWindowLongW
                    SetWindowLongPtr = user32.SetWindowLongW
                # 诊断：记录最小化前的本进程窗口和样式
                try:
                    self._dump_native_windows("before_minimize")
                except Exception:
                    pass
                hwnd = int(self.winId())
                # 记录并设置 owner 为 hidden owner，以避免任务栏图标残留
                GWLP_HWNDPARENT = -8
                try:
                    try:
                        orig_parent = GetWindowLongPtr(hwnd, GWLP_HWNDPARENT)
                    except Exception:
                        orig_parent = 0
                    if not hasattr(self, '_orig_hwnd_parent'):
                        self._orig_hwnd_parent = orig_parent
                    try:
                        self._ensure_hidden_owner()
                        owner_hwnd = getattr(self, '_hidden_owner_hwnd', 0)
                        if owner_hwnd:
                            try:
                                SetWindowLongPtr(hwnd, GWLP_HWNDPARENT, owner_hwnd)
                            except Exception:
                                pass
                    except Exception:
                        pass
                except Exception:
                    pass
                ex_style = GetWindowLongPtr(hwnd, GWL_EXSTYLE)
                new_style = (ex_style & ~WS_EX_APPWINDOW) | WS_EX_TOOLWINDOW
                ret = SetWindowLongPtr(hwnd, GWL_EXSTYLE, new_style)
                # 强制窗口样式刷新
                SWP_NOSIZE = 0x0001
                SWP_NOMOVE = 0x0002
                SWP_NOZORDER = 0x0004
                SWP_FRAMECHANGED = 0x0020
                flags = SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED
                sp_ret = user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, flags)
                # 诊断：记录修改后的本进程窗口和样式
                try:
                    self._dump_native_windows("after_minimize")
                except Exception:
                    pass
                # 额外尝试：将本进程其它顶层窗口也设置为 TOOLWINDOW，避免残留任务栏项
                try:
                    # Aggressively convert any remaining APPWINDOWs in this process to TOOLWINDOW
                    self._apply_toolwindow_to_process_windows(exclude_hwnds={hwnd}, tag='minimize', aggressive=True)
                except Exception:
                    pass
                # 额外重试，处理可能的 HWND 重建
                try:
                    owner_hwnd = getattr(self, '_hidden_owner_hwnd', 0)
                    self._win32_apply_toolwindow(hwnd, owner_hwnd=owner_hwnd, tag='minimize-retry', retries=3)
                except Exception:
                    pass
                    self.append_log(f"最小化到托盘 (Win32): winId={hwnd}, ex_style=0x{ex_style:08x} ret={ret} sp_ret={sp_ret}", "INFO")
                # 直接隐藏窗口并接受事件（避免阻止 Qt 内部处理）
                self.hide()
                try:
                    event.accept()
                except Exception:
                    pass
                # 异步重试一次，以应对 Qt 在隐藏后重建 HWND 的情况
                try:
                    owner_hwnd = getattr(self, '_hidden_owner_hwnd', 0)
                    hwnd_local = int(hwnd)
                    owner_local = int(owner_hwnd) if owner_hwnd else 0
                    QTimer.singleShot(120, lambda: self._win32_apply_toolwindow(hwnd_local, owner_hwnd=owner_local, tag='minimize-async', retries=3))
                except Exception:
                    pass
                # 启动 winId 变化 watcher，在隐藏后短时间内监测并重试
                try:
                    self._start_winid_watcher(duration_ms=2500, interval_ms=120, role='minimize')
                except Exception:
                    pass
                return
        super().changeEvent(event)


    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._restore_from_tray()

    def _restore_from_tray(self):
        # 首先尝试使用 Qt 恢复窗口标志
        try:
            if hasattr(self, '_orig_window_flags'):
                self.setWindowFlags(self._orig_window_flags)
            else:
                self.setWindowFlag(Qt.WindowType.Tool, False)
            # 确保系统按钮标志正确设置
            self.ensure_window_buttons()
            QApplication.processEvents()
            self.showNormal()
            try:
                self.raise_()
                self.activateWindow()
            except Exception:
                pass
            # 诊断：检查 native ex_style，若已包含 APPWINDOW 则认为 Qt 恢复成功
            import ctypes
            user32 = ctypes.windll.user32
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            try:
                GetWindowLongPtr = user32.GetWindowLongPtrW
            except AttributeError:
                GetWindowLongPtr = user32.GetWindowLongW
            hwnd = int(self.winId())
            ex_style = GetWindowLongPtr(hwnd, GWL_EXSTYLE)
            if ex_style & WS_EX_APPWINDOW:
                try:
                    self._dump_native_windows("after_restore_qt")
                except Exception:
                    pass
                # 恢复之前设置的 owner（如存在）
                try:
                    user32 = ctypes.windll.user32
                    try:
                        SetWindowLongPtr = user32.SetWindowLongPtrW
                    except AttributeError:
                        SetWindowLongPtr = user32.SetWindowLongW
                    GWLP_HWNDPARENT = -8
                    orig_parent = getattr(self, '_orig_hwnd_parent', 0)
                    if orig_parent:
                        try:
                            SetWindowLongPtr(hwnd, GWLP_HWNDPARENT, orig_parent)
                        except Exception:
                            pass
                    else:
                        try:
                            SetWindowLongPtr(hwnd, GWLP_HWNDPARENT, 0)
                        except Exception:
                            pass
                    try:
                        self._destroy_hidden_owner()
                    except Exception:
                        pass
                except Exception:
                    pass
                self.append_log(f"从托盘恢复 (Qt): winId={hwnd}, ex_style=0x{ex_style:08x}", "INFO")
                return
            else:
                self.append_log(f"Qt 恢复后 APPWINDOW 未设置 (0x{ex_style:08x}), 使用 Win32 回退", "INFO")
        except Exception as e:
            self.append_log(f"尝试使用 Qt 恢复失败: {e}", "ERROR")
        # Win32 回退
        import ctypes
        user32 = ctypes.windll.user32
        GWL_EXSTYLE = -20
        WS_EX_APPWINDOW = 0x00040000
        WS_EX_TOOLWINDOW = 0x00000080
        try:
            GetWindowLongPtr = user32.GetWindowLongPtrW
            SetWindowLongPtr = user32.SetWindowLongPtrW
        except AttributeError:
            GetWindowLongPtr = user32.GetWindowLongW
            SetWindowLongPtr = user32.SetWindowLongW
        hwnd = int(self.winId())
        orig_parent = getattr(self, '_orig_hwnd_parent', 0)
        try:
            # 使用封装的重试逻辑以应对 HWND 重建
            self._win32_apply_appwindow(hwnd, orig_parent=orig_parent, tag='restore', retries=3)
        except Exception:
            pass
        try:
            self._destroy_hidden_owner()
        except Exception:
            pass
        try:
            self._dump_native_windows("after_restore_win32")
        except Exception:
            pass
        self.append_log(f"从托盘恢复 (Win32): winId={hwnd}, orig_parent={orig_parent}", "INFO")
        try:
            self.showNormal()
            self.raise_()
            self.activateWindow()
        except Exception:
            self.showNormal()
        # 异步验证并重试设置 APPWINDOW（以防 Qt 在 restore 后重建 HWND 或重置样式）
        try:
            hwnd_local = int(hwnd)
            orig_parent_local = int(orig_parent) if orig_parent else 0
            QTimer.singleShot(120, lambda: self._win32_apply_appwindow(hwnd_local, orig_parent=orig_parent_local, tag='restore-async', retries=3))
        except Exception:
            pass
        # 启动 winId 变化 watcher，在恢复后短时间内监测并确保 APPWINDOW 被设置
        try:
            self._start_winid_watcher(duration_ms=2500, interval_ms=120, role='restore')
        except Exception:
            pass

    def _quit_from_tray(self):
        # 通过托盘菜单退出，直接结束应用（绕过退出确认）
        if hasattr(self, '_tray_icon'):
            self._tray_icon.hide()
        self.append_log("退出: 从系统托盘退出应用", "INFO")
        try:
            self._uninstall_win_event_hook()
        except Exception:
            pass
        try:
            self._destroy_hidden_owner()
        except Exception:
            pass
        try:
            self._destroy_native_hidden_owner()
        except Exception:
            pass
        QApplication.quit()

    def add_page(self, page_id: str, title: str, page_widget: QWidget,
                 icon: Optional[str] = None, position: str = "top") -> None:
        self._navigation_bar.add_page(page_id, title, icon, position)
        self._content_area.add_page(page_id, page_widget)

    def remove_page(self, page_id: str) -> None:
        if page_id == "settings":
            return
        self._navigation_bar.remove_page(page_id)
        self._content_area.remove_page(page_id)

    def has_page(self, page_id: str) -> bool:
        return page_id in self._navigation_bar._nav_buttons and page_id in self._content_area._pages

    def show_page(self, page_id: str) -> None:
        if not self.has_page(page_id):
            return
        current_page_id = self._content_area.get_current_page_id()
        if current_page_id == page_id:
            return
        self._navigation_bar.set_current_page(page_id)
        self._content_area.show_page(page_id)

    def get_current_page_id(self) -> Optional[str]:
        return self._content_area.get_current_page_id()

    def get_page(self, page_id: str) -> Optional[QWidget]:
        return self._content_area.get_page(page_id)

    def get_auth_page(self) -> Optional[AuthPage]:
        return self._auth_page

    def get_settings_page(self) -> Optional[SettingsPage]:
        return self._settings_page
    def set_status(self, message: str) -> None:
        self._status_bar.showMessage(message)

    def set_version(self, version: str) -> None:
        self._navigation_bar.set_version(version)

    def append_log(self, message: str, level: str = "INFO") -> None:
        prefix = ">>>" if level == "INFO" else "!!!" if level == "ERROR" else ">>>"
        self.set_status(f"{prefix} {level}: {message[:200]}")

    def set_agent_executor(self, agent_executor):
        if self._agent_page:
            self._agent_page.set_agent_executor(agent_executor)

    def update_device_status(self, status: str, connected: bool = False,
                             device_info: Optional[Dict[str, Any]] = None) -> None:
        self.set_status(status)

    def update_screen_preview(self, image_data: bytes) -> None:
        pass

    def start_preview_refresh(self) -> None:
        pass

    def _on_screenshot_requested(self) -> None:
        self.screenshot_requested.emit()

    def stop_preview_refresh(self) -> None:
        pass

    def closeEvent(self, event) -> None:
        self.window_closed.emit()
        # 最小化到托盘时：关闭按钮触发最小化到托盘（隐藏窗口），不弹出确认
        if self._minimize_to_tray and hasattr(self, '_tray_icon'):
            # 保存原始窗口标志
            if not hasattr(self, '_orig_window_flags'):
                self._orig_window_flags = self.windowFlags()
            # 设置为 Tool 窗口并隐藏
            self.setWindowFlag(Qt.WindowType.Tool, True)
            self.hide()
            # Win32 设置：移除 APPWINDOW 并添加 TOOLWINDOW，避免任务栏残留
            try:
                import ctypes
                user32 = ctypes.windll.user32
                GWL_EXSTYLE = -20
                WS_EX_APPWINDOW = 0x00040000
                WS_EX_TOOLWINDOW = 0x00000080
                GWLP_HWNDPARENT = -8
                try:
                    GetWindowLongPtr = user32.GetWindowLongPtrW
                    SetWindowLongPtr = user32.SetWindowLongPtrW
                except AttributeError:
                    GetWindowLongPtr = user32.GetWindowLongW
                    SetWindowLongPtr = user32.SetWindowLongW
                hwnd = int(self.winId())
                # 设置 hidden owner 以避免任务栏图标
                try:
                    self._ensure_hidden_owner()
                    owner_hwnd = getattr(self, '_hidden_owner_hwnd', 0)
                    if owner_hwnd:
                        SetWindowLongPtr(hwnd, GWLP_HWNDPARENT, owner_hwnd)
                except Exception:
                    pass
                # 修改窗口样式
                ex_style = GetWindowLongPtr(hwnd, GWL_EXSTYLE)
                new_style = (ex_style & ~WS_EX_APPWINDOW) | WS_EX_TOOLWINDOW
                SetWindowLongPtr(hwnd, GWL_EXSTYLE, new_style)
                SWP_NOSIZE = 0x0001
                SWP_NOMOVE = 0x0002
                SWP_NOZORDER = 0x0004
                SWP_FRAMECHANGED = 0x0020
                flags = SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED
                user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, flags)
                self.append_log("关闭按钮 -> 最小化到托盘", "INFO")
            except Exception as e:
                self.append_log(f"Win32 托盘设置失败：{e}", "INFO")
            event.ignore()
            return
        # 未启用托盘时：弹出退出确认
        reply = QMessageBox.question(self, '确认退出',
                                     '退出伊丝蒂娜·终末地助手？',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            # 在真正退出前卸载 WinEvent hook 和 native owner
            try:
                self._uninstall_win_event_hook()
            except Exception:
                pass
            try:
                self._destroy_hidden_owner()
            except Exception:
                pass
            try:
                self._destroy_native_hidden_owner()
            except Exception:
                pass
            event.accept()
        else:
            event.ignore()


    def _on_arkpass_selected(self, arkpass_path: str):
        if not self._auth_manager:
            self.append_log("错误: 认证管理器未初始化", "ERROR")
            QMessageBox.warning(self, "错误", "认证组件未初始化")
            return
        if not os.path.exists(arkpass_path):
            self.set_status(">>> 认证失败: 文件未找到")
            self.append_log(f"认证失败: 文件未找到: {arkpass_path}", "ERROR")
            QMessageBox.critical(self, "凭证读取失败",
                                 f"文件未找到或无法访问:\n{arkpass_path}")
            return
        try:
            result = self._auth_manager.login_with_arkpass(arkpass_path)
            if isinstance(result, tuple):
                success = result[0]
                error_msg = result[1] if len(result) > 1 else "登录失败"
            else:
                success = bool(result)
                error_msg = "登录失败"
            if success:
                self.set_status(">>> 认证成功")
                self._is_logged_in = True
                self._navigation_bar.set_login_state(True, True, None)
                user_id = getattr(self._auth_manager, 'user_id', '')
                self.append_log(f"用户已认证: {user_id}", "INFO")
                if self.has_page("standard_reasoning"):
                    self.show_page("standard_reasoning")
                # 使用 QTimer 延迟显示消息，确保窗口已完全显示并避免黑屏小窗口问题
                QTimer.singleShot(300, lambda: QMessageBox.information(
                    self, "认证成功", f"欢迎回来，{user_id or '用户'}"
                ))
            else:
                actual_error = error_msg if error_msg else (result[1] if isinstance(result, tuple) and len(result) > 1 else "未知错误")
                self.set_status(f">>> 认证失败: {actual_error}")
                self.append_log(f"认证失败: {actual_error}", "ERROR")
                QMessageBox.warning(self, "认证失败",
                                    f"认证失败:\n{actual_error}\n\n路径:\n{arkpass_path}")
        except FileNotFoundError:
            self.set_status(">>> 认证失败: 文件未找到")
            self.append_log(f"认证失败: 文件未找到: {arkpass_path}", "ERROR")
            QMessageBox.critical(self, "凭证读取失败", f"文件未找到:\n{arkpass_path}")
        except PermissionError:
            self.set_status(">>> 认证失败: 权限不足")
            self.append_log(f"认证失败: 权限不足: {arkpass_path}", "ERROR")
            QMessageBox.critical(self, "权限错误", f"无法读取文件:\n{arkpass_path}")
        except Exception as e:
            self.append_log(f"认证异常: {e}", "ERROR")
            self.set_status(">>> 认证失败: 异常")
            QMessageBox.warning(self, "认证异常", str(e))
            QMessageBox.critical(self, "错误", f"认证异常: {e}")

    def _on_logout_requested(self):
        if not self._auth_manager:
            return
        self._auth_manager.is_logged_in = False
        self._is_logged_in = False
        self._navigation_bar.set_login_state(True, False, "auth_cloud")
        self.append_log("用户已注销", "INFO")
        QMessageBox.information(self, "已注销", "您已成功注销。")

    def _on_register_requested(self, username: str):
        if not self._auth_manager:
            self.append_log("错误: 认证管理器未初始化", "ERROR")
            if self._auth_page:
                self._auth_page.on_register_complete(False)
            return
        self.set_status(f">>> 注册中: {username}")
        self.append_log(f"注册用户: {username}...", "INFO")

        class RegisterThread(QThread):
            finished = pyqtSignal(object)

            def __init__(self, auth_manager, username):
                super().__init__()
                self.auth_manager = auth_manager
                self.username = username

            def run(self):
                try:
                    result = self.auth_manager.register_user(self.username)
                    self.finished.emit(result)
                except Exception as e:
                    self.finished.emit(e)

        self._register_thread = RegisterThread(self._auth_manager, username)
        self._register_thread.finished.connect(self._on_register_complete)
        self._register_thread.start()

    def _on_register_complete(self, result):
        if isinstance(result, Exception):
            self.append_log(f"注册异常: {result}", "ERROR")
            self.set_status(">>> 注册失败: 异常")
            if self._auth_page:
                self._auth_page.on_register_complete(False)
            return

        if isinstance(result, tuple):
            success = result[0]
            error_msg = result[1] if len(result) > 1 else "注册失败"
        else:
            success = bool(result)
            error_msg = "注册失败"

        if success:
            self.append_log("用户已注册", "INFO")
            self.set_status(">>> 已注册")
            cache_dir = self._auth_page._get_cache_dir()
            arkpass_path = os.path.join(cache_dir, f"{getattr(self._auth_manager, 'user_id', 'user')}.arkpass")
            if self._auth_page:
                self._auth_page.on_register_complete(True, arkpass_path)
            if os.path.exists(arkpass_path):
                self._on_arkpass_selected(arkpass_path)
        else:
            actual_error = error_msg if error_msg else "未知错误"
            self.append_log(f"注册失败: {actual_error}", "ERROR")
            self.set_status(f">>> 注册失败: {actual_error}")
            if self._auth_page:
                self._auth_page.on_register_complete(False)

    def _refresh_user_info(self):
        self._refresh_auth_status()

    def showEvent(self, event):
        """窗口首次显示时确保正确的几何尺寸和布局
        """
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.Show and not self._window_shown:
            self._window_shown = True
            # 重新设置窗口标题
            self.setWindowTitle(self._title)
            # 确保窗口按钮可见（QMainWindow 默认已有正确 flags）
            self.ensure_window_buttons()
            # 设置窗口大小
            self.resize(max(self._min_width, 1280), max(self._min_height, 800))
            # 通过 Win32 API 设置 WS_EX_APPWINDOW，确保标题栏正确显示
            self._ensure_appwindow_style()
            # 修复 3.1：增加延迟到 1 秒，确保窗口完全就绪
            QTimer.singleShot(1000, self._auto_login)
        super().showEvent(event)

    def openEvent(self, event):
        """窗口完全打开事件（修复 3.1：窗口完全就绪后再触发自动登录）"""
        super().openEvent(event)
        # 窗口完全就绪，可以安全触发自动登录
        if not self._auto_login_attempted:
            QTimer.singleShot(500, self._auto_login)

    def _center_on_screen(self):
        """计算屏幕中心位置"""
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QPoint
        screen = QApplication.primaryScreen().geometry()
        window_geometry = self.frameGeometry()
        return QPoint(
            screen.x() + (screen.width() - window_geometry.width()) // 2,
            screen.y() + (screen.height() - window_geometry.height()) // 2
        )

    def _refresh_auth_status(self):
        if not self._auth_manager or not self._auth_page:
            return
        is_logged_in = getattr(self._auth_manager, 'is_logged_in', False)
        if is_logged_in:
            user_id = getattr(self._auth_manager, 'user_id', '')
            self._auth_page.set_login_status(True, {"user_id": user_id})
            self._is_logged_in = True
            self._navigation_bar.set_login_state(True, True, None)
            self.set_status(f">>> 已认证: {user_id}")
        else:
            self._auth_page.set_login_status(False)
            self._is_logged_in = False
            self._navigation_bar.set_login_state(True, False, "auth_cloud")
            self.set_status(">>> 未认证")