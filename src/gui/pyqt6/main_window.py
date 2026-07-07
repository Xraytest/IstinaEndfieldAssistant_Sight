from __future__ import annotations

from typing import Callable, Optional

from pathlib import Path

from PyQt6.QtCore import QSettings, QTimer, Qt
from PyQt6.QtGui import QCloseEvent, QCursor, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)
from gui.pyqt6.theme.widget_styles import PREVIEW_STYLE, PANEL_STYLE

from core.foundation.gpu_check import check_gpu, format_gpu_warning
from core.foundation.paths import ensure_src_path
from gui.pyqt6.cli_bridge import CLIBridge
from gui.pyqt6.i18n import get_locale_manager
from gui.pyqt6.pages.device_settings_page import DeviceSettingsPage
from gui.pyqt6.pages.log_page import LogPage
from gui.pyqt6.pages.maaend_control_page import MaaEndControlPage
from gui.pyqt6.pages.prts_full_intelligence_page import PrtsFullIntelligencePage
from gui.pyqt6.pages.settings_page import SettingsPage
from gui.pyqt6.scripting.scripting_page import ScriptingPage
from gui.pyqt6.dashboard.dashboard_page import DashboardPage
from gui.pyqt6.responsive import apply_ui_mode, clamp_window_size, fade_widget, ui_mode_for_size
from gui.pyqt6.tray_icon import TrayIcon

ensure_src_path(__file__)
locale = get_locale_manager()


class MainWindow(QMainWindow):
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        bridge_factory: Optional[Callable[[], CLIBridge]] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(locale.tr("app_title", "IstinaEndfieldAssistant Sight"))
        self.setMinimumSize(800, 600)
        self._bridge = bridge_factory() if bridge_factory is not None else CLIBridge(self)
        if self._bridge.parent() is None:
            self._bridge.setParent(self)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)
        self.setCentralWidget(central)

        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage(locale.tr("status_ready", "Ready"))
        self.statusBar().setAccessibleName("status_bar")
        self.statusBar().setAccessibleDescription("status_bar_desc")

        self._navigation_list: Optional[QListWidget] = None
        self._page_stack: Optional[QStackedWidget] = None
        self._preview_label: Optional[QLabel] = None
        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(1500)
        self._preview_timer.timeout.connect(self._refresh_preview)
        self._tray_icon: Optional[TrayIcon] = None
        self._title_animation_timer = QTimer(self)
        self._title_animation_timer.timeout.connect(self._animate_title)
        self._is_executing = False
        self._build_shell()
        self._restore_or_fit_window()
        self._update_responsive_mode()
        self._setup_tray_icon()

        QTimer.singleShot(0, self._show_gpu_warning_if_needed)
        QTimer.singleShot(0, self._async_warmup)
        self._setup_keyboard_shortcuts()

    def _setup_keyboard_shortcuts(self) -> None:
        """Setup keyboard shortcuts for navigation and actions."""
        pages = self._page_stack.count() if self._page_stack else 0
        for i in range(min(pages, 5)):
            shortcut = QShortcut(f"Ctrl+{i+1}", self)
            shortcut.activated.connect(lambda idx=i: self._on_nav_changed(idx))

        refresh_shortcut = QShortcut("F5", self)
        refresh_shortcut.activated.connect(self._refresh_preview)

        theme_shortcut = QShortcut("Ctrl+T", self)
        theme_shortcut.activated.connect(self._cycle_theme)

    def _setup_tray_icon(self) -> None:
        """Setup system tray icon for minimize-to-tray support."""
        self._tray_icon = TrayIcon(self)

    def _cycle_theme(self) -> None:
        """Cycle through available themes."""
        from gui.pyqt6.theme.theme_manager import get_theme
        theme_manager = get_theme()
        themes = theme_manager.get_available_themes()
        if not themes:
            return
        current = theme_manager.get_current_theme()
        current_index = next((i for i, t in enumerate(themes) if t["id"] == current), -1)
        next_index = (current_index + 1) % len(themes)
        next_theme = themes[next_index]["id"]
        theme_manager.set_current_theme(next_theme)
        app = QApplication.instance()
        if app is not None:
            theme_manager.apply_theme(app, next_theme)
        self.statusBar().showMessage(locale.tr("theme_switched", "Theme switched"), 2000)

    def _async_warmup(self) -> None:
        self._bridge.execute("llm start", {})

    def _show_gpu_warning_if_needed(self) -> None:
        result = check_gpu()
        message = format_gpu_warning(result)
        if message is None:
            return
        title = locale.tr("gpu_warning_title", "GPU Not Supported") if not result.is_nvidia else locale.tr("gpu_low_vram_title", "Low GPU VRAM")
        QMessageBox.warning(self, title, message)

    def closeEvent(self, event: QCloseEvent) -> None:
        settings = QSettings("ArkStudio", "IstinaEndfieldAssistant")
        settings.setValue("mainWindow/geometry", self.saveGeometry())
        self._bridge.execute("llm stop", {})
        if self._tray_icon is not None and self._tray_icon.is_available():
            event.ignore()
            self.hide()
            self._tray_icon.show_message(locale.tr("app_title", "IstinaEndfieldAssistant Sight"), locale.tr("tray_minimized", "Minimized to tray. Double-click tray icon to restore."))
        else:
            super().closeEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_responsive_mode()

    def _build_shell(self) -> None:
        root_layout = self.centralWidget().layout()

        hero = QFrame(self)
        hero.setObjectName("heroPanel")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(14, 10, 14, 10)
        hero_layout.setSpacing(12)

        title_label = QLabel("Istina Endfield Assistant")
        title_label.setProperty("variant", "hero")
        title_label.setAccessibleName("app_title")
        title_label.setAccessibleDescription("Istina Endfield Assistant 主窗口标题")
        hero_layout.addWidget(title_label)
        hero_layout.addStretch()
        root_layout.addWidget(hero)

        shell = QWidget(self)
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(12)

        nav_panel = QWidget(shell)
        nav_layout = QVBoxLayout(nav_panel)
        nav_layout.setContentsMargins(10, 10, 10, 10)
        nav_layout.setSpacing(8)

        nav_title = QLabel(locale.tr("nav_pages", "Pages"))
        nav_title.setProperty("variant", "eyebrow")
        nav_title.setAccessibleName("nav_pages")
        nav_layout.addWidget(nav_title)

        self._navigation_list = QListWidget(nav_panel)
        self._navigation_list.setObjectName("mainNavigation")
        self._navigation_list.setFixedWidth(220)
        self._navigation_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._navigation_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._navigation_list.currentRowChanged.connect(self._on_nav_changed)
        self._navigation_list.setAccessibleName("nav_list")
        self._navigation_list.setAccessibleDescription("nav_list_desc")
        nav_layout.addWidget(self._navigation_list)

        self._preview_label = QLabel(locale.tr("preview_empty", "No preview"))
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet(PREVIEW_STYLE)
        self._preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._preview_label.setMinimumHeight(160)
        self._preview_label.setAccessibleName("preview_area")
        self._preview_label.setAccessibleDescription("preview_area_desc")
        nav_layout.addWidget(self._preview_label, 1)

        shell_layout.addWidget(nav_panel, 0, Qt.AlignmentFlag.AlignTop)

        content_panel = QFrame(shell)
        content_panel.setObjectName("contentPanel")
        content_panel.setStyleSheet(PANEL_STYLE)
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(0)

        self._page_stack = QStackedWidget(content_panel)
        content_layout.addWidget(self._page_stack)
        shell_layout.addWidget(content_panel, 1)

        self._maaend_page = MaaEndControlPage(bridge=self._bridge)
        self._device_page = DeviceSettingsPage(bridge=self._bridge)
        self._scripting_page = ScriptingPage(main_window=self)
        self._dashboard_page = DashboardPage(bridge=self._bridge)
        pages = [
            (locale.tr("dashboard_title", "Dashboard"), self._dashboard_page),
            (locale.tr("prts_title", "PRTS Intelligence"), PrtsFullIntelligencePage(bridge=self._bridge)),
            (locale.tr("maaend_title", "Standard Inference"), self._maaend_page),
            (locale.tr("device_title", "Device"), self._device_page),
            (locale.tr("settings_title", "Settings"), SettingsPage()),
            (locale.tr("log_title", "Logs"), LogPage()),
            (locale.tr("scripting_title", "Scripting"), self._scripting_page),
        ]
        for label, page in pages:
            item = QListWidgetItem(label)
            key = {
                "PRTS全智能": "nav_prts",
                "标准推理": "nav_maaend",
                "设备": "nav_device",
                "设置": "nav_settings",
                "日志": "nav_log",
                "Scripting": "nav_scripting",
            }.get(label, label)
            item.setData(Qt.ItemDataRole.AccessibleTextRole, key)
            item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, locale.tr(key, f"Switch to {label} page"))
            self._navigation_list.addItem(item)
            self._page_stack.addWidget(page)

        from gui.pyqt6.theme.icons import apply_nav_icons
        apply_nav_icons(self._navigation_list)

        self._bridge.commandFinished.connect(self._on_bridge_command_finished)
        self._maaend_page.execution_state_changed.connect(self._on_execution_state_changed)

        self._resize_navigation_list()
        for i in range(self._navigation_list.count()):
            if self._navigation_list.item(i).text() == "标准推理":
                self._navigation_list.setCurrentRow(i)
                break
        root_layout.addWidget(shell, 1)

    def _restore_or_fit_window(self) -> None:
        settings = QSettings("ArkStudio", "IstinaEndfieldAssistant")
        geometry = settings.value("mainWindow/geometry")
        if geometry is not None and self.restoreGeometry(geometry):
            return

        screen = self.screen()
        if screen is None:
            self.resize(1280, 800)
            return
        target = clamp_window_size(screen.availableGeometry().size(), (1440, 900), (800, 600))
        self.resize(target)

    def _update_responsive_mode(self) -> None:
        mode = ui_mode_for_size(self.size())
        apply_ui_mode(self, mode)
        central = self.centralWidget()
        if central is not None:
            apply_ui_mode(central, mode)
            layout = central.layout()
            if layout is not None:
                from gui.pyqt6.responsive import get_dpi_scale, scale_value
                scale = get_dpi_scale(self)
                if mode == "compact":
                    layout.setContentsMargins(
                        scale_value(10, scale), scale_value(10, scale),
                        scale_value(10, scale), scale_value(8, scale)
                    )
                    layout.setSpacing(scale_value(6, scale))
                else:
                    layout.setContentsMargins(
                        scale_value(16, scale), scale_value(16, scale),
                        scale_value(16, scale), scale_value(12, scale)
                    )
                    layout.setSpacing(scale_value(10, scale))
        navigation_list = getattr(self, "_navigation_list", None)
        if navigation_list is not None:
            navigation_list.setFixedWidth(180 if mode == "compact" else 220)

    def _on_nav_changed(self, index: int) -> None:
        if self._page_stack is None or index < 0:
            return
        self._page_stack.setCurrentIndex(index)
        page = self._page_stack.currentWidget()
        if page is not None:
            fade_widget(page, duration=180)
        self._preview_timer.start()

    def _on_bridge_command_finished(self, command: str, result: dict) -> None:
        """同步设备页与标准推理页的连接状态。"""
        if command.startswith("system connect"):
            if result.get("status") == "success":
                self._maaend_page.set_connected(True)
                QTimer.singleShot(0, self._refresh_preview)
            else:
                self._maaend_page.set_connected(False)
                self._maaend_page.set_auto_connect_attempted()
        elif command.startswith("system disconnect"):
            self._maaend_page.set_connected(False)

    def _on_execution_state_changed(self, is_executing: bool) -> None:
        self._is_executing = is_executing
        if is_executing:
            self._preview_timer.stop()
            self._title_animation_timer.start(500)
            QApplication.setOverrideCursor(QCursor(Qt.CursorShape.BusyCursor))
            self._set_taskbar_progress(0)
        else:
            if self._page_stack.currentIndex() == 1:
                self._preview_timer.start()
            self._title_animation_timer.stop()
            self.setWindowTitle(locale.tr("app_title", "IstinaEndfieldAssistant Sight"))
            QApplication.restoreOverrideCursor()
            self._set_taskbar_progress(100)
            QTimer.singleShot(1000, lambda: self._set_taskbar_progress(0))

    def _animate_title(self) -> None:
        if not self._is_executing:
            return
        base = locale.tr("app_title", "IstinaEndfieldAssistant Sight")
        dots = "..." * ((self._title_animation_timer.interval() // 500) % 4)
        self.setWindowTitle(f"{base} {dots}")

    def _set_taskbar_progress(self, value: int) -> None:
        # Placeholder for Windows taskbar progress integration.
        # Full implementation would use ITaskbarList3 via COM.
        pass

    def _refresh_preview(self) -> None:
        if self._preview_label is None:
            return
        if not self._maaend_page._connected:
            return
        if self._maaend_page._is_executing:
            return  # 任务执行期间不刷新预览
        result = self._maaend_page._sync_execute("screenshot", timeout_ms=5000)
        if not result or result.get("status") != "success":
            return
        data = result.get("base64")
        if not data:
            path = result.get("path")
            if path:
                try:
                    data = Path(path).read_bytes()
                except Exception:
                    return
            else:
                return
        try:
            import base64
            image_data = base64.b64decode(data)
        except Exception:
            return
        pixmap = QPixmap()
        if pixmap.loadFromData(image_data):
            scaled = pixmap.scaled(self._preview_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self._preview_label.setPixmap(scaled)

    def _resize_navigation_list(self) -> None:
        if self._navigation_list is None:
            return
        frame = self._navigation_list.frameWidth() * 2
        row_height = self._navigation_list.sizeHintForRow(0) if self._navigation_list.count() else 36
        total_height = frame + (row_height * self._navigation_list.count()) + 8
        self._navigation_list.setFixedHeight(total_height)

    def bridge(self) -> CLIBridge:
        return self._bridge
