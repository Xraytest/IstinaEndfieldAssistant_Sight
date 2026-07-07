from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import QSettings, QTimer, Qt
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
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
from gui.pyqt6.pages.maaend_control_page import PREVIEW_STYLE

from core.foundation.gpu_check import check_gpu, format_gpu_warning
from core.foundation.paths import ensure_src_path
from gui.pyqt6.cli_bridge import CLIBridge
from gui.pyqt6.pages.device_settings_page import DeviceSettingsPage
from gui.pyqt6.pages.log_page import LogPage
from gui.pyqt6.pages.maaend_control_page import MaaEndControlPage
from gui.pyqt6.pages.prts_full_intelligence_page import PrtsFullIntelligencePage
from gui.pyqt6.pages.settings_page import SettingsPage
from gui.pyqt6.responsive import apply_ui_mode, clamp_window_size, ui_mode_for_size

from PyQt6.QtCore import QTimer

ensure_src_path(__file__)


class MainWindow(QMainWindow):
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        bridge_factory: Optional[Callable[[], CLIBridge]] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("IstinaEndfieldAssistant Sight")
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
        self.statusBar().showMessage("界面已就绪")

        self._navigation_list: Optional[QListWidget] = None
        self._page_stack: Optional[QStackedWidget] = None
        self._preview_label: Optional[QLabel] = None
        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(1500)
        self._preview_timer.timeout.connect(self._refresh_preview)
        self._build_shell()
        self._restore_or_fit_window()
        self._update_responsive_mode()

        QTimer.singleShot(0, self._show_gpu_warning_if_needed)
        QTimer.singleShot(0, self._async_warmup)

    def _async_warmup(self) -> None:
        self._bridge.execute("llm start", {})

    def _show_gpu_warning_if_needed(self) -> None:
        result = check_gpu()
        message = format_gpu_warning(result)
        if message is None:
            return
        title = "GPU不受支持" if not result.is_nvidia else "GPU显存低"
        QMessageBox.warning(self, title, message)

    def closeEvent(self, event: QCloseEvent) -> None:
        settings = QSettings("ArkStudio", "IstinaEndfieldAssistant")
        settings.setValue("mainWindow/geometry", self.saveGeometry())
        self._bridge.execute("llm stop", {})
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

        nav_title = QLabel("页面")
        nav_title.setProperty("variant", "eyebrow")
        nav_layout.addWidget(nav_title)

        self._navigation_list = QListWidget(nav_panel)
        self._navigation_list.setObjectName("mainNavigation")
        self._navigation_list.setFixedWidth(220)
        self._navigation_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._navigation_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._navigation_list.currentRowChanged.connect(self._on_nav_changed)
        nav_layout.addWidget(self._navigation_list)

        self._preview_label = QLabel("暂无预览")
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet(PREVIEW_STYLE)
        self._preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._preview_label.setMinimumHeight(160)
        nav_layout.addWidget(self._preview_label, 1)

        shell_layout.addWidget(nav_panel, 0, Qt.AlignmentFlag.AlignTop)

        content_panel = QFrame(shell)
        content_panel.setObjectName("contentPanel")
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(0)

        self._page_stack = QStackedWidget(content_panel)
        content_layout.addWidget(self._page_stack)
        shell_layout.addWidget(content_panel, 1)

        self._maaend_page = MaaEndControlPage(bridge=self._bridge)
        self._device_page = DeviceSettingsPage(bridge=self._bridge)
        pages = [
            ("PRTS全智能", PrtsFullIntelligencePage(bridge=self._bridge)),
            ("标准推理", self._maaend_page),
            ("设备", self._device_page),
            ("设置", SettingsPage()),
            ("日志", LogPage()),
        ]
        for label, page in pages:
            self._navigation_list.addItem(QListWidgetItem(label))
            self._page_stack.addWidget(page)

        self._bridge.commandFinished.connect(self._on_bridge_command_finished)

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
                if mode == "compact":
                    layout.setContentsMargins(10, 10, 10, 8)
                    layout.setSpacing(6)
                else:
                    layout.setContentsMargins(16, 16, 16, 12)
                    layout.setSpacing(10)
        navigation_list = getattr(self, "_navigation_list", None)
        if navigation_list is not None:
            navigation_list.setFixedWidth(180 if mode == "compact" else 220)

    def _on_nav_changed(self, index: int) -> None:
        if self._page_stack is None or index < 0:
            return
        self._page_stack.setCurrentIndex(index)
        if index == 1:  # 标准推理页
            self._preview_timer.start()
        else:
            self._preview_timer.stop()

    def _on_bridge_command_finished(self, command: str, result: dict) -> None:
        """同步设备页与标准推理页的连接状态。"""
        if command.startswith("system connect"):
            if result.get("status") == "success":
                self._maaend_page.set_connected(True)
            else:
                self._maaend_page.set_connected(False)
                self._maaend_page.set_auto_connect_attempted()
        elif command.startswith("system disconnect"):
            self._maaend_page.set_connected(False)

    def _refresh_preview(self) -> None:
        if self._preview_label is None:
            return
        current_widget = self._page_stack.currentWidget()
        if isinstance(current_widget, MaaEndControlPage):
            if not current_widget._connected:
                return
            result = current_widget._sync_execute("screenshot")
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
