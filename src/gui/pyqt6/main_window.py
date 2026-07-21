from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import QRect, QSettings, QSize, Qt, QTimer
from PyQt6.QtGui import QBrush, QCloseEvent, QColor, QCursor, QFont, QFontMetrics, QLinearGradient, QPainter, QPen, QPixmap, QShortcut
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

from core.foundation.gpu_check import check_gpu, format_gpu_warning
from core.foundation.logger import LogCategory, get_logger
from core.foundation.paths import ensure_src_path, get_project_root
from gui.pyqt6.cli_bridge import CLIBridge
from gui.pyqt6.i18n import get_locale_manager
from gui.pyqt6.pages.device_settings_page import DeviceSettingsPage
from gui.pyqt6.pages.log_page import LogPage
from gui.pyqt6.pages.maaend_control_page import MaaEndControlPage
from gui.pyqt6.pages.prts_full_intelligence_page import PrtsFullIntelligencePage
from gui.pyqt6.pages.scheduled_tasks_page import ScheduledTasksPage
from gui.pyqt6.pages.settings_page import SettingsPage
from gui.pyqt6.preview_worker import PreviewWorker
from gui.pyqt6.responsive import apply_ui_mode, clamp_window_size, fade_widget, ui_mode_for_size
from gui.pyqt6.theme.icons import apply_nav_icons
from gui.pyqt6.theme.widget_styles import PANEL_STYLE
from gui.pyqt6.tray_icon import TrayIcon

ensure_src_path(__file__)
locale = get_locale_manager()


# 预览状态色值（与 theme_manager.py 中 COLORS 保持一致）
_STATUS_COLOR_LIVE = "#19d1ff"          # primary
_STATUS_COLOR_IDLE = "#8a8ea4"         # text_secondary
_STATUS_COLOR_LOST = "#e03131"          # danger


class PreviewWidget(QWidget):
    """预览画面 widget，在 pixmap 上叠加右下角状态角标。

    性能优化：
      - 静态背景层（渐变 sheen + corner accents + frame）缓存为 QPixmap，
        仅在 size 变化时重建；paintEvent 直接 drawPixmap，避免每帧重算渐变。
      - 状态角标 pill 按 (text, color) 缓存为 QPixmap，命中即直接绘制。
      - set_pixmap / set_status 加状态比较，无变化时不触发 update()，
        避免 30fps 轮询每次都重绘未变化的状态。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: Optional[QPixmap] = None
        self._status_text: str = ""
        self._status_color: str = _STATUS_COLOR_IDLE
        # 状态比较：避免重复 update()
        self._last_pixmap_key: Optional[int] = None
        self._last_status: Optional[tuple] = None
        # 静态背景缓存（渐变 + corner accents + frame）
        self._bg_cache: Optional[QPixmap] = None
        self._bg_cache_size: QSize = QSize()
        # badge pill 缓存：(text, color) -> QPixmap
        self._badge_cache: dict[tuple[str, str], QPixmap] = {}
        self.setFixedSize(220, 124)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_pixmap(self, pixmap: Optional[QPixmap]) -> None:
        # 用 cacheKey 判断是否真有新帧，避免相同 pixmap 重复 update
        key = pixmap.cacheKey() if pixmap is not None and not pixmap.isNull() else None
        if key == self._last_pixmap_key:
            return
        self._last_pixmap_key = key
        self._pixmap = pixmap
        self.update()

    def clear_pixmap(self) -> None:
        if self._pixmap is None:
            return
        self._pixmap = None
        self._last_pixmap_key = None
        self.update()

    def set_status(self, text: str, color: str = _STATUS_COLOR_IDLE) -> None:
        if self._last_status == (text, color):
            return
        self._last_status = (text, color)
        self._status_text = text
        self._status_color = color
        self.update()

    def _rebuild_bg_cache(self) -> None:
        """重建静态背景缓存。仅在 size 变化时调用。"""
        rect = self.rect()
        pixmap = QPixmap(rect.size())
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Base canvas
        painter.fillRect(rect, QColor(8, 8, 12))
        # Subtle top sheen for depth
        sheen = QLinearGradient(0, 0, 0, rect.height())
        sheen.setColorAt(0.0, QColor(25, 209, 255, 10))
        sheen.setColorAt(0.45, QColor(25, 209, 255, 0))
        painter.fillRect(rect, QBrush(sheen))

        # Industrial corner accent brackets
        self._draw_corner_accents(painter, rect, 7, QColor(25, 209, 255, 120))

        # Frame
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(25, 209, 255, 40), 1))
        painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), 4, 4)
        painter.end()
        self._bg_cache = pixmap
        self._bg_cache_size = rect.size()

    def _get_badge_pixmap(self, text: str, color: str) -> QPixmap:
        """获取状态角标 pill 的 QPixmap，按 (text, color) 缓存。"""
        key = (text, color)
        cached = self._badge_cache.get(key)
        if cached is not None:
            return cached
        # 渲染到 QPixmap
        badge_font = QFont()
        badge_font.setPointSize(8)
        badge_font.setBold(True)
        fm = QFontMetrics(badge_font)
        text_w = fm.horizontalAdvance(text)
        text_h = fm.ascent()
        pad_x, pad_y = 8, 4
        pill_w = text_w + pad_x * 2
        pill_h = text_h + pad_y * 2
        pixmap = QPixmap(pill_w, pill_h)
        pixmap.fill(Qt.GlobalColor.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        status_col = QColor(color)
        pill_bg = QColor(status_col)
        pill_bg.setAlpha(58)
        p.setBrush(QBrush(pill_bg))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, pill_w, pill_h, pill_h / 2, pill_h / 2)
        p.setPen(status_col)
        p.setFont(badge_font)
        p.drawText(QRect(0, 0, pill_w, pill_h), Qt.AlignmentFlag.AlignCenter, text)
        p.end()
        self._badge_cache[key] = pixmap
        return pixmap

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        # 1. 静态背景层：缓存命中直接 drawPixmap（30fps 下避免重算渐变）
        if self._bg_cache is None or self._bg_cache_size != rect.size():
            self._rebuild_bg_cache()
        if self._bg_cache is not None:
            painter.drawPixmap(0, 0, self._bg_cache)

        # 2. 动态 pixmap（scaled 仍每次算，但只此一处开销）
        if self._pixmap is not None and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                rect.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (rect.width() - scaled.width()) // 2
            y = (rect.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            empty_font = QFont()
            empty_font.setPointSize(8)
            painter.setFont(empty_font)
            painter.setPen(QColor(_STATUS_COLOR_IDLE))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, locale.tr("preview_empty", "No preview"))
            # Thin accent rule beneath the placeholder for a finished look
            rule_w = 36
            rule_x = rect.center().x() - rule_w // 2
            rule_y = rect.center().y() + 14
            painter.setPen(QPen(QColor(25, 209, 255, 45), 1))
            painter.drawLine(rule_x, rule_y, rule_x + rule_w, rule_y)

        # 3. badge pill：缓存命中直接 drawPixmap（无字体度量/绘制开销）
        if self._status_text:
            badge = self._get_badge_pixmap(self._status_text, self._status_color)
            margin = 6
            painter.drawPixmap(
                rect.right() - margin - badge.width(),
                rect.bottom() - margin - badge.height(),
                badge,
            )

        painter.end()

    def _draw_corner_accents(self, painter: QPainter, rect, length: int, color: QColor) -> None:
        pen = QPen(color, 1.4)
        painter.setPen(pen)
        tl = rect.topLeft()
        br = rect.bottomRight()
        # top-left
        painter.drawLine(tl.x(), tl.y(), tl.x() + length, tl.y())
        painter.drawLine(tl.x(), tl.y(), tl.x(), tl.y() + length)
        # top-right
        painter.drawLine(br.x(), tl.y(), br.x() - length, tl.y())
        painter.drawLine(br.x(), tl.y(), br.x(), tl.y() + length)
        # bottom-left
        painter.drawLine(tl.x(), br.y(), tl.x() + length, br.y())
        painter.drawLine(tl.x(), br.y(), tl.x(), br.y() - length)
        # bottom-right
        painter.drawLine(br.x(), br.y(), br.x() - length, br.y())
        painter.drawLine(br.x(), br.y(), br.x(), br.y() - length)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # size 变化后让 paintEvent 重建缓存
        self._bg_cache = None


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
        self._logger = get_logger(__name__)

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
        self._preview_widget: Optional[PreviewWidget] = None
        self._frame_worker: Optional["PreviewWorker"] = None
        self._tray_icon: Optional[TrayIcon] = None
        self._title_animation_timer = QTimer(self)
        self._title_animation_timer.timeout.connect(self._animate_title)
        self._is_executing = False
        self._build_shell()
        self._restore_or_fit_window()
        self._update_responsive_mode()
        self._setup_tray_icon()

        QTimer.singleShot(0, self._show_gpu_warning_if_needed)
        self._setup_keyboard_shortcuts()

    def _setup_keyboard_shortcuts(self) -> None:
        """Setup keyboard shortcuts for navigation and actions."""
        pages = self._page_stack.count() if self._page_stack else 0
        for i in range(pages):
            shortcut = QShortcut(f"Ctrl+{i+1}", self)
            shortcut.activated.connect(lambda idx=i: self._on_nav_changed(idx))

        # F5: 强制刷新预览（重启 worker）
        refresh_shortcut = QShortcut("F5", self)
        refresh_shortcut.activated.connect(self._restart_preview_worker)

    def _setup_tray_icon(self) -> None:
        """Setup system tray icon for minimize-to-tray support."""
        self._tray_icon = TrayIcon(self)

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
        if self._tray_icon is not None and self._tray_icon.is_available():
            event.ignore()
            self.hide()
            self._tray_icon.show_message(locale.tr("app_title", "IstinaEndfieldAssistant Sight"), locale.tr("tray_minimized", "Minimized to tray. Double-click tray icon to restore."))
        else:
            maaend_page = getattr(self, "_maaend_page", None)
            if maaend_page is not None:
                try:
                    maaend_page._persist_state()
                except Exception as exc:
                    self._logger.warning(LogCategory.GUI, "closeEvent 持久化队列状态失败", error=str(exc))
            scheduled_page = getattr(self, "_scheduled_page", None)
            if scheduled_page is not None:
                try:
                    scheduled_page.shutdown()
                except Exception as exc:
                    self._logger.warning(LogCategory.GUI, "closeEvent 停止定时任务调度器失败", error=str(exc))
            self._stop_frame_worker()
            super().closeEvent(event)

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        # 托盘最小化时保持运行状态不变：PreviewWorker 持续读取 mmap、CLI 进程
        # 不受影响。scrcpy 持续传输，正在执行的任务不中断。
        self._logger.info(LogCategory.GUI, "窗口隐藏（最小化到托盘），运行状态保持不变")

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # 窗口恢复时确保 worker 运行（防御性：托盘期间若因其他逻辑停止）
        if hasattr(self, "_maaend_page") and self._maaend_page._connected:
            if self._frame_worker is None:
                self._start_frame_worker()

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

        self._preview_widget = PreviewWidget()
        self._preview_widget.setAccessibleName("preview_area")
        self._preview_widget.setAccessibleDescription("preview_area_desc")
        nav_layout.addWidget(self._preview_widget, 1)

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
        self._prts_page = PrtsFullIntelligencePage(bridge=self._bridge)
        self._scheduled_page = ScheduledTasksPage(bridge=self._bridge)
        pages = [
            (locale.tr("prts_title", "PRTS Intelligence (施工中)"), self._prts_page),
            (locale.tr("maaend_title", "Standard Inference"), self._maaend_page),
            (locale.tr("sched_title", "Scheduled Tasks"), self._scheduled_page),
            (locale.tr("device_title", "Device"), self._device_page),
            (locale.tr("settings_title", "Settings"), SettingsPage()),
            (locale.tr("log_title", "Logs"), LogPage()),
        ]
        for label, page in pages:
            item = QListWidgetItem(label)
            key = {
                "PRTS全智能": "nav_prts",
                "标准推理": "nav_maaend",
                "定时任务": "nav_sched",
                "设备": "nav_device",
                "设置": "nav_settings",
                "日志": "nav_log",
            }.get(label, label)
            item.setData(Qt.ItemDataRole.AccessibleTextRole, key)
            item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, locale.tr(key, f"Switch to {label} page"))
            self._navigation_list.addItem(item)
            self._page_stack.addWidget(page)

        self._navigation_list.setIconSize(QSize(18, 18))
        apply_nav_icons(self._navigation_list)

        self._bridge.commandFinished.connect(self._on_bridge_command_finished)
        self._bridge.processCrashed.connect(self._on_cli_crashed)
        self._maaend_page.execution_state_changed.connect(self._on_execution_state_changed)
        # 将标准推理页引用注入定时任务页，使调度器执行日志统一打印到标准推理页日志面板
        self._scheduled_page.set_maaend_page(self._maaend_page)

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
        preview_widget = getattr(self, "_preview_widget", None)
        if preview_widget is not None:
            width = 180 if mode == "compact" else 220
            height = max(101, int(width * 9 / 16))
            preview_widget.setFixedSize(width, height)

    def _on_nav_changed(self, index: int) -> None:
        if self._page_stack is None or index < 0:
            return
        self._page_stack.setCurrentIndex(index)
        page = self._page_stack.currentWidget()
        if page is not None:
            fade_widget(page, duration=180)
        # 预览由 PreviewWorker 持续驱动，无需在页面切换时启动 timer

    def _on_bridge_command_finished(self, command: str, result: dict) -> None:
        """同步设备页与标准推理页的连接状态。"""
        if command.startswith("system connect"):
            if result.get("status") == "success":
                self._maaend_page.set_connected(True)
                # 启动 PreviewWorker 替代旧的 timer 轮询
                self._stop_frame_worker()
                self._start_frame_worker()
            else:
                self._maaend_page.set_connected(False)
                self._maaend_page.set_auto_connect_attempted()
                self._stop_frame_worker()
                if self._preview_widget is not None:
                    self._preview_widget.set_status(locale.tr("preview_status_disconnected", "已断开"), _STATUS_COLOR_LOST)
        elif command.startswith("system disconnect"):
            self._maaend_page.set_connected(False)
            self._stop_frame_worker()
            if self._preview_widget is not None:
                self._preview_widget.set_status(locale.tr("preview_status_disconnected", "已断开"), _STATUS_COLOR_LOST)

    def _on_cli_crashed(self, crash_count: int) -> None:
        """CLI 进程崩溃时保持运行状态，自动重连设备。

        不标记断开、不停止 frame worker。CLIBridge 在 1s 后自动重启 CLI 进程，
        本方法在 1.5s 后（留 0.5s 给新进程初始化）自动重新发起 system connect，
        使新 daemon 启动 scrcpy 会话并写入新的 mmap 帧。worker 通过 refresh()
        检测到新 daemon 后无缝切换到新 mmap，实现 scrcpy 持续传输。
        """
        self._logger.warning(LogCategory.GUI, "CLI 崩溃，保持运行状态并计划自动重连", crash_count=crash_count)
        if not self._maaend_page._connected:
            return
        QTimer.singleShot(1500, self._auto_reconnect_after_crash)

    def _auto_reconnect_after_crash(self) -> None:
        """CLI 崩溃重启后自动重新连接设备，恢复 scrcpy 传输。"""
        if not self._maaend_page._connected:
            return
        params = self._maaend_page._resolve_connect_params()
        serial = params.get("serial") if params else None
        if not serial:
            serial = self._resolve_preview_serial()
            if not serial:
                return
            params = {"serial": serial}
        self._logger.info(LogCategory.GUI, "CLI 崩溃后自动重连设备", serial=serial)
        self._bridge.execute("system connect", params)

    def _on_execution_state_changed(self, is_executing: bool) -> None:
        self._is_executing = is_executing
        if is_executing:
            self._title_animation_timer.start(500)
            QApplication.setOverrideCursor(QCursor(Qt.CursorShape.BusyCursor))
            self._set_taskbar_progress(0)
        else:
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

    # ------------------------------------------------------------------
    # Preview worker（替代旧的 _preview_timer + _refresh_preview 轮询路径）
    # ------------------------------------------------------------------
    def _start_frame_worker(self) -> None:
        """启动 PreviewWorker 后台读取 scrcpy mmap 帧。"""
        if self._frame_worker is not None:
            return
        if not self._maaend_page._connected:
            return
        serial = self._resolve_preview_serial()
        if not serial:
            return
        worker = PreviewWorker(serial, parent=self)
        worker.frame_ready.connect(self._on_frame_ready)
        worker.status_changed.connect(self._on_worker_status)
        self._frame_worker = worker
        worker.start()
        self._logger.info(LogCategory.GUI, "PreviewWorker 已启动", serial=serial)

    def _stop_frame_worker(self) -> None:
        if self._frame_worker is not None:
            try:
                self._frame_worker.stop()
            except Exception:
                pass
            self._frame_worker = None

    def _restart_preview_worker(self) -> None:
        """F5 强制刷新：停止并重启 worker（用于诊断）。"""
        self._stop_frame_worker()
        if self._maaend_page._connected:
            self._start_frame_worker()

    def _on_frame_ready(self, img: QImage) -> None:
        """主线程槽：从 worker 接收帧，跳帧策略取最新 pending。"""
        if self._preview_widget is None or self._frame_worker is None:
            return
        # 跳帧：若 worker 端有更新的 pending 帧，取最新
        pending = self._frame_worker.consume_pending()
        if pending is not None:
            img = pending
        if img is None or img.isNull():
            return
        pixmap = QPixmap.fromImage(img)
        self._preview_widget.set_pixmap(pixmap)
        # status 由 worker.status_changed 统一设置，此处不再每帧重复 set_status

    def _on_worker_status(self, text: str, color: str) -> None:
        if self._preview_widget is not None:
            self._preview_widget.set_status(text, color)

    def _resize_navigation_list(self) -> None:
        if self._navigation_list is None:
            return
        frame = self._navigation_list.frameWidth() * 2
        row_height = self._navigation_list.sizeHintForRow(0) if self._navigation_list.count() else 36
        total_height = frame + (row_height * self._navigation_list.count()) + 8
        self._navigation_list.setFixedHeight(total_height)

    def _resolve_preview_serial(self) -> Optional[str]:
        try:
            config = json.loads((get_project_root() / "config" / "client_config.json").read_text(encoding="utf-8"))
            return ((config.get("device") or {}).get("last_connected")) or ((config.get("device") or {}).get("serial"))
        except Exception:
            return None

    def bridge(self) -> CLIBridge:
        return self._bridge
