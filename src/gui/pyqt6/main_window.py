from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import QRect, QSettings, QSize, Qt, QTimer
from PyQt6.QtGui import QBrush, QCloseEvent, QColor, QCursor, QFont, QFontMetrics, QLinearGradient, QPainter, QPen, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
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
from gui.pyqt6.instance import InstanceManager, InstanceSidebarWidget
from gui.pyqt6.instance.dialogs import (
    ConfirmDeleteDialog,
    NewInstanceDialog,
    RecolorInstanceDialog,
    RenameInstanceDialog,
)
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

        # 多实例管理器：注册表 + 活动实例 + 上下文缓存
        self._instance_mgr = InstanceManager(parent=self)

        # 兼容旧 API：保留 self._bridge 指向活动实例的 bridge
        # 在 _on_instance_changed 中会同步更新
        self._bridge_factory = bridge_factory
        active_ctx = self._instance_mgr.get_active_context()
        self._bridge = active_ctx.bridge

        self._logger = get_logger(__name__)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
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
        # 区分"真退出"与"最小化到托盘"：托盘菜单退出 / 应用退出流程设置 True，
        # closeEvent 据此走资源清理 + super().closeEvent，不再最小化并提示。
        self._force_quit: bool = False
        self._build_shell()
        self._restore_or_fit_window()
        self._update_responsive_mode()
        self._setup_tray_icon()

        # 实例管理器初始化（启动活动实例的调度器）
        self._instance_mgr.initialize()
        # 绑定实例切换信号
        self._instance_mgr.instance_changed.connect(self._on_instance_changed)
        self._instance_mgr.instance_created.connect(self._on_instance_created)
        self._instance_mgr.instance_deleted.connect(self._on_instance_deleted)
        self._instance_mgr.instance_meta_changed.connect(self._on_instance_meta_changed)
        # 监听活动实例的任务/连接状态变化
        for ctx in self._instance_mgr._contexts.values():
            self._bind_context_signals(ctx)

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

    def quit_application(self) -> None:
        """托盘菜单"退出"入口：标记真退出，触发 closeEvent 走完整清理流程。

        与直接调用 QApplication.quit() 的区别：
          - QApplication.quit() 仅退出事件循环，跳过 closeEvent 资源清理
            （_persist_state / scheduled_page.shutdown / _stop_frame_worker），
            且退出过程中 Qt 可能因 setQuitOnLastWindowClosed(True) 派发
            closeEvent，此时 tray 仍可用会被当作"最小化"。
          - 本方法设置 _force_quit=True 后调用 self.close()，closeEvent 据此
            走真退出分支，完成清理后 super().closeEvent(event) 接受关闭，
            最后一个窗口关闭后 QApplication 自然退出。
        """
        self._force_quit = True
        self.close()

    def _show_gpu_warning_if_needed(self) -> None:
        result = check_gpu()
        message = format_gpu_warning(result)
        if message is None:
            return
        title = locale.tr("gpu_warning_title", "GPU Not Supported") if not result.is_nvidia else locale.tr("gpu_low_vram_title", "Low GPU VRAM")
        QMessageBox.warning(self, title, message)

    def closeEvent(self, event: QCloseEvent) -> None:
        settings = QSettings("ArkStudio", "IstinaEndfieldAssistant")
        # 多实例：geometry 按实例 id 隔离持久化
        try:
            from core.foundation.instance import get_instance_id
            iid = get_instance_id()
        except Exception:
            iid = "default"
        settings.setValue(f"instances/{iid}/mainWindow/geometry", self.saveGeometry())
        # 兼容旧 key（保持 default 实例行为不变）
        if iid == "default":
            settings.setValue("mainWindow/geometry", self.saveGeometry())
        # _force_quit 由托盘菜单"退出"显式设置，应用退出流程派发的 closeEvent
        # 也视作真退出；只有用户点 X / Alt+F4 且托盘可用时才最小化到托盘。
        is_real_quit = self._force_quit or self._tray_icon is None or not self._tray_icon.is_available()
        if not is_real_quit:
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

        # 主体（hero + shell）放在一个外层 QWidget 中，便于统一设置内边距
        body = QWidget(self)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 16, 16, 12)
        body_layout.setSpacing(10)
        root_layout.addWidget(body, 1)

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
        # 当前实例指示器（hero 右侧）
        self._instance_indicator_label = QLabel("")
        self._instance_indicator_label.setStyleSheet(
            "color: #8a8ea4; font-size: 12px; padding: 2px 10px;"
            " border: 1px solid #2d3038; border-radius: 10px;"
        )
        hero_layout.addWidget(self._instance_indicator_label)
        body_layout.addWidget(hero)

        shell = QWidget(self)
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(8)

        # 最左侧：实例切换侧栏
        self._instance_sidebar = InstanceSidebarWidget(shell)
        self._instance_sidebar.instance_activated.connect(self._on_sidebar_instance_activated)
        self._instance_sidebar.create_requested.connect(self._on_sidebar_create_requested)
        self._instance_sidebar.rename_requested.connect(self._on_sidebar_rename_requested)
        self._instance_sidebar.recolor_requested.connect(self._on_sidebar_recolor_requested)
        self._instance_sidebar.clone_requested.connect(self._on_sidebar_clone_requested)
        self._instance_sidebar.delete_requested.connect(self._on_sidebar_delete_requested)
        self._instance_sidebar.open_in_explorer_requested.connect(self._on_sidebar_open_in_explorer)
        # 初始化侧栏内容
        self._instance_sidebar.set_instances(self._instance_mgr.list_metas())
        self._instance_sidebar.set_active(self._instance_mgr.active_id)
        shell_layout.addWidget(self._instance_sidebar, 0, Qt.AlignmentFlag.AlignTop)

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

        # 使用活动实例的 bridge 构造页面
        active_ctx = self._instance_mgr.get_active_context()
        active_store = active_ctx.task_store
        active_scheduler = active_ctx.scheduler
        self._maaend_page = MaaEndControlPage(bridge=self._bridge)
        self._device_page = DeviceSettingsPage(bridge=self._bridge)
        self._prts_page = PrtsFullIntelligencePage(bridge=self._bridge)
        self._scheduled_page = ScheduledTasksPage(
            bridge=self._bridge, store=active_store, scheduler=active_scheduler
        )
        self._settings_page = SettingsPage()
        pages = [
            (locale.tr("prts_title", "PRTS Intelligence (施工中)"), self._prts_page),
            (locale.tr("maaend_title", "Standard Inference"), self._maaend_page),
            (locale.tr("sched_title", "Scheduled Tasks"), self._scheduled_page),
            (locale.tr("device_title", "Device"), self._device_page),
            (locale.tr("settings_title", "Settings"), self._settings_page),
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
        body_layout.addWidget(shell, 1)

        # 更新实例指示器
        self._update_instance_indicator()

    def _restore_or_fit_window(self) -> None:
        settings = QSettings("ArkStudio", "IstinaEndfieldAssistant")
        # 多实例：geometry 按实例 id 隔离
        try:
            from core.foundation.instance import get_instance_id
            iid = get_instance_id()
        except Exception:
            iid = "default"
        geometry = settings.value(f"instances/{iid}/mainWindow/geometry")
        if geometry is None:
            # 向后兼容：旧 key
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
        # 同步到当前实例的 task_running 状态（驱动 sidebar 红点）
        try:
            active_ctx = self._instance_mgr.get_active_context()
            active_ctx.set_task_running(is_executing)
        except Exception:
            pass
        if is_executing:
            self._title_animation_timer.start(500)
            QApplication.setOverrideCursor(QCursor(Qt.CursorShape.BusyCursor))
            self._set_taskbar_progress(0)
        else:
            self._title_animation_timer.stop()
            self._update_window_title()
            QApplication.restoreOverrideCursor()
            self._set_taskbar_progress(100)
            QTimer.singleShot(1000, lambda: self._set_taskbar_progress(0))

    # ------------------------------------------------------------------
    # 多实例：sidebar 事件处理 + 实例切换分发
    # ------------------------------------------------------------------
    def _bind_context_signals(self, ctx: "InstanceContext") -> None:
        """绑定实例上下文的状态变化信号到 sidebar。"""
        try:
            ctx.task_running_changed.connect(self._instance_sidebar.set_task_running)
            ctx.connection_changed.connect(self._instance_sidebar.set_connected)
            ctx.completed_unread_changed.connect(self._instance_sidebar.set_completed_unread)
            # 调度器繁忙状态：非活动实例任务完成时标记"完成且未读"
            scheduler = ctx.scheduler
            iid = ctx.id
            busy_signal = getattr(scheduler, "busy_state_changed", None)
            if busy_signal is not None and not getattr(scheduler, "_iea_bound_completed", False):
                busy_signal.connect(lambda busy, _iid=iid: self._on_scheduler_busy_changed(_iid, busy))
                scheduler._iea_bound_completed = True
        except Exception:
            pass

    def _on_scheduler_busy_changed(self, instance_id: str, busy: bool) -> None:
        """调度器繁忙状态变化：任务完成时若非活动实例则标记未读。"""
        if busy:
            return
        try:
            if instance_id == self._instance_mgr.active_id:
                return
            ctx = self._instance_mgr.get_context(instance_id)
            ctx.set_completed_unread(True)
        except Exception:
            pass

    def _update_instance_indicator(self) -> None:
        """更新 hero 右侧的实例指示器。"""
        try:
            ctx = self._instance_mgr.get_active_context()
            meta = ctx.meta
            self._instance_indicator_label.setText(meta.display_name)
            self._instance_indicator_label.setStyleSheet(
                f"color: {meta.color}; font-size: 12px; padding: 2px 10px;"
                f" border: 1px solid {meta.color}; border-radius: 10px;"
            )
        except Exception:
            self._instance_indicator_label.setText("")

    def _update_window_title(self) -> None:
        """更新窗口标题（含实例名）。"""
        base = locale.tr("app_title", "IstinaEndfieldAssistant Sight")
        try:
            ctx = self._instance_mgr.get_active_context()
            meta = ctx.meta
            if not meta.is_default:
                self.setWindowTitle(f"{base} [{meta.display_name}]")
            else:
                self.setWindowTitle(base)
        except Exception:
            self.setWindowTitle(base)

    def _on_sidebar_instance_activated(self, instance_id: str) -> None:
        """侧栏点击切换实例。"""
        # 切换前若当前实例有任务在执行，弹确认
        try:
            current_ctx = self._instance_mgr.get_active_context()
            if current_ctx.is_task_running:
                reply = QMessageBox.warning(
                    self,
                    locale.tr("instance_switch_running_title", "任务执行中"),
                    locale.tr(
                        "instance_switch_running_msg",
                        "当前实例正在执行任务，切换实例可能中断预览。是否继续？"
                    ),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
        except Exception:
            pass
        self._instance_mgr.set_active(instance_id)

    def _on_instance_changed(self, instance_id: str) -> None:
        """实例切换后的分发逻辑：刷新页面、状态栏、预览。"""
        ctx = self._instance_mgr.get_context(instance_id)
        # 0. 清除"完成且未读"状态（用户已切回该实例，绿点消除）
        if ctx.is_completed_unread:
            ctx.set_completed_unread(False)
        # 1. 停止旧实例的预览 worker
        self._stop_frame_worker()
        # 2. 同步 self._bridge 到新实例的 bridge
        self._bridge.commandFinished.disconnect(self._on_bridge_command_finished)
        self._bridge.processCrashed.disconnect(self._on_cli_crashed)
        self._bridge = ctx.bridge
        self._bridge.commandFinished.connect(self._on_bridge_command_finished)
        self._bridge.processCrashed.connect(self._on_cli_crashed)
        # 3. 通知各页面刷新（pages 自行实现 on_instance_changed）
        self._dispatch_instance_changed_to_pages(ctx)
        # 4. 更新侧栏选中态
        self._instance_sidebar.set_active(instance_id)
        # 5. 更新窗口标题 + 实例指示器
        self._update_window_title()
        self._update_instance_indicator()
        # 6. 启动新实例的预览 worker（若已连接）
        if ctx.is_connected:
            self._start_frame_worker()
        else:
            if self._preview_widget is not None:
                self._preview_widget.clear_pixmap()
                self._preview_widget.set_status(
                    locale.tr("preview_status_disconnected", "已断开"), _STATUS_COLOR_LOST
                )
        # 7. 绑定信号（首次加载该实例时）
        self._bind_context_signals(ctx)

    def _dispatch_instance_changed_to_pages(self, ctx: "InstanceContext") -> None:
        """将实例上下文变化分发到各页面。

        每个页面可选实现 ``on_instance_changed(ctx)`` 方法，未实现则跳过。
        """
        for page in (self._maaend_page, self._device_page, self._prts_page,
                     self._scheduled_page, self._settings_page):
            handler = getattr(page, "on_instance_changed", None)
            if handler is None:
                continue
            try:
                handler(ctx)
            except Exception as exc:
                self._logger.warning(LogCategory.GUI, "页面 on_instance_changed 异常",
                                     page=type(page).__name__, error=str(exc))

    def _on_instance_created(self, instance_id: str) -> None:
        """新实例创建后刷新侧栏。"""
        self._instance_sidebar.set_instances(self._instance_mgr.list_metas())

    def _on_instance_deleted(self, instance_id: str) -> None:
        """实例删除后刷新侧栏。"""
        self._instance_sidebar.set_instances(self._instance_mgr.list_metas())

    def _on_instance_meta_changed(self, instance_id: str) -> None:
        """实例元数据变化（重命名/改色/改图标）。"""
        meta = self._instance_mgr.registry.get_meta(instance_id)
        if meta is not None:
            self._instance_sidebar.update_meta(meta)
        # 若是活动实例，刷新标题与指示器
        if instance_id == self._instance_mgr.active_id:
            self._update_window_title()
            self._update_instance_indicator()

    def _on_sidebar_create_requested(self) -> None:
        """新建实例。"""
        dlg = NewInstanceDialog(self._instance_mgr.list_metas(), parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        name, color, clone_from = dlg.get_values()
        try:
            new_id = self._instance_mgr.create(
                display_name=name, color=color, clone_from=clone_from
            )
            # 询问是否立即切换到新实例
            reply = QMessageBox.question(
                self,
                locale.tr("instance_created_title", "实例已创建"),
                locale.tr(
                    "instance_created_msg",
                    "实例 \"{name}\" 已创建。是否立即切换到该实例？"
                ).format(name=name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._instance_mgr.set_active(new_id)
        except Exception as exc:
            QMessageBox.critical(
                self,
                locale.tr("instance_create_failed_title", "创建失败"),
                str(exc),
            )

    def _on_sidebar_rename_requested(self, instance_id: str) -> None:
        meta = self._instance_mgr.registry.get_meta(instance_id)
        if meta is None:
            return
        dlg = RenameInstanceDialog(meta.display_name, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_name = dlg.get_name()
        self._instance_mgr.update_meta(instance_id, display_name=new_name)

    def _on_sidebar_recolor_requested(self, instance_id: str) -> None:
        meta = self._instance_mgr.registry.get_meta(instance_id)
        if meta is None:
            return
        dlg = RecolorInstanceDialog(meta.color, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._instance_mgr.update_meta(instance_id, color=dlg.get_color())

    def _on_sidebar_clone_requested(self, instance_id: str) -> None:
        """克隆实例：直接以新名创建，clone_from=instance_id。"""
        meta = self._instance_mgr.registry.get_meta(instance_id)
        if meta is None:
            return
        dlg = NewInstanceDialog(self._instance_mgr.list_metas(), parent=self)
        # 预填：克隆来源锁定为源实例
        for i in range(dlg._clone_combo.count()):
            if dlg._clone_combo.itemData(i) == instance_id:
                dlg._clone_combo.setCurrentIndex(i)
                break
        dlg.setWindowTitle(locale.tr("instance_clone_title", "克隆实例"))
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        name, color, _ = dlg.get_values()
        try:
            self._instance_mgr.create(
                display_name=name, color=color, clone_from=instance_id
            )
        except Exception as exc:
            QMessageBox.critical(self, "", str(exc))

    def _on_sidebar_delete_requested(self, instance_id: str) -> None:
        meta = self._instance_mgr.registry.get_meta(instance_id)
        if meta is None:
            return
        if meta.is_default:
            QMessageBox.information(
                self,
                locale.tr("instance_delete_default_title", "无法删除"),
                locale.tr("instance_delete_default_msg", "default 实例不可删除"),
            )
            return
        dlg = ConfirmDeleteDialog(meta, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        if dlg.get_confirm_text() != meta.display_name:
            QMessageBox.warning(
                self,
                locale.tr("instance_delete_mismatch_title", "名称不匹配"),
                locale.tr("instance_delete_mismatch_msg", "输入的名称与实例名不匹配，已取消删除"),
            )
            return
        try:
            self._instance_mgr.delete(instance_id)
        except Exception as exc:
            QMessageBox.critical(self, "", str(exc))

    def _on_sidebar_open_in_explorer(self, instance_id: str) -> None:
        """在文件管理器中打开实例目录。"""
        from core.foundation.instance import get_instance_root
        import subprocess
        import sys
        path = str(get_instance_root(instance_id))
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["explorer", path])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as exc:
            self._logger.warning(LogCategory.GUI, "打开文件管理器失败", error=str(exc))

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
            from core.foundation.instance import get_instance_root
            config_path = get_instance_root() / "config" / "client_config.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            return ((config.get("device") or {}).get("last_connected")) or ((config.get("device") or {}).get("serial"))
        except Exception:
            return None

    def bridge(self) -> CLIBridge:
        return self._bridge
