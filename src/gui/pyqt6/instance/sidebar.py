"""最左侧实例切换侧栏。

显示所有实例的图标列表，支持点击切换、右键上下文菜单、新建实例。
"""
from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import (
    QPropertyAnimation,
    QPoint,
    QRect,
    QSize,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QContextMenuEvent,
    QEnterEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPalette,
    QPen,
    QPixmap,
    QResizeEvent,
)
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.foundation.logger import LogCategory, get_logger
from gui.pyqt6.i18n import get_locale_manager
from .registry import InstanceMeta


locale = get_locale_manager()


class InstanceItemWidget(QFrame):
    """单个实例项：图标 + 名称 + 状态指示。

    视觉状态：
        - 选中：左侧 3px 强调条（meta.color）+ 浅色背景
        - 未选中：透明背景
        - 任务运行中：右上角蓝点（呼吸动画）
        - 完成且未读（处于其他实例未返回）：右上角绿点
        - 空闲：右上角白点
        - 断线：右下角叹号
        - 鼠标悬停：浅色背景
    """

    clicked = pyqtSignal(str)  # instance_id
    context_menu_requested = pyqtSignal(str, QPoint)  # instance_id, global_pos

    ITEM_SIZE = QSize(56, 56)

    # 状态点颜色
    _DOT_COLOR_IDLE = QColor(212, 212, 216)      # 白色（d4d4d8，与名称同色系）
    _DOT_COLOR_RUNNING = QColor(25, 209, 255)     # 蓝色（主题 primary #19d1ff）
    _DOT_COLOR_COMPLETED = QColor(34, 197, 94)    # 绿色（#22c55e）

    def __init__(self, meta: InstanceMeta, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._meta = meta
        self._is_active = False
        self._is_hovered = False
        self._task_running = False
        self._completed_unread = False
        self._connected = True  # 默认认为已连接（无设备时也显示正常）
        self._breath_opacity = 0.0
        self._breath_anim: Optional[QPropertyAnimation] = None

        self.setFixedSize(self.ITEM_SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # 名称 label（最多 4 字符）— 不再显示 emoji 图标
        name = meta.display_name or meta.id
        if len(name) > 4:
            name = name[:4]
        self._name_label = QLabel(name, self)
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name_label.setStyleSheet(
            "font-size: 13px; color: #d4d4d8; background: transparent;"
        )
        layout.addStretch()
        layout.addWidget(self._name_label)
        layout.addStretch()

        self._update_style()

    # ------------------------------------------------------------------
    # 属性
    # ------------------------------------------------------------------
    @property
    def instance_id(self) -> str:
        return self._meta.id

    @property
    def meta(self) -> InstanceMeta:
        return self._meta

    def update_meta(self, meta: InstanceMeta) -> None:
        self._meta = meta
        name = meta.display_name or meta.id
        if len(name) > 4:
            name = name[:4]
        self._name_label.setText(name)
        self._update_style()

    def set_active(self, active: bool) -> None:
        if self._is_active == active:
            return
        self._is_active = active
        self._update_style()
        self.update()

    def set_task_running(self, running: bool) -> None:
        if self._task_running == running:
            return
        self._task_running = running
        if running:
            self._start_breath()
        else:
            self._stop_breath()
        self.update()

    def set_completed_unread(self, unread: bool) -> None:
        """设置"完成且未读"状态（绿色点）。

        优先级低于 task_running：若任务正在运行，仍显示运行蓝点。
        """
        if self._completed_unread == unread:
            return
        self._completed_unread = unread
        self.update()

    def set_connected(self, connected: bool) -> None:
        if self._connected == connected:
            return
        self._connected = connected
        self.update()

    # ------------------------------------------------------------------
    # 视觉
    # ------------------------------------------------------------------
    def _update_style(self) -> None:
        # 强调条与背景色通过 paintEvent 绘制，这里仅设置基础样式
        border_color = self._meta.color if self._is_active else "transparent"
        bg = "rgba(255,255,255,0.04)" if not self._is_active else "rgba(255,255,255,0.08)"
        self.setStyleSheet(
            f"InstanceItemWidget {{ background: {bg}; border: 1px solid {border_color};"
            f" border-radius: 8px; }}"
        )

    def _start_breath(self) -> None:
        if self._breath_anim is not None:
            return
        # 用窗口属性做呼吸效果（opacity 0~1 循环）
        # 这里用 _breath_opacity + QTimer 简化
        self._breath_phase = 0.0
        self._breath_timer = QTimer(self)
        self._breath_timer.setInterval(50)
        self._breath_timer.timeout.connect(self._on_breath_tick)
        self._breath_timer.start()

    def _stop_breath(self) -> None:
        timer = getattr(self, "_breath_timer", None)
        if timer is not None:
            timer.stop()
            timer.deleteLater()
            self._breath_timer = None
        self._breath_opacity = 0.0
        self.update()

    def _on_breath_tick(self) -> None:
        import math
        import time
        self._breath_phase = (getattr(self, "_breath_phase", 0.0) + 0.08) % (2 * math.pi)
        self._breath_opacity = 0.5 + 0.5 * math.sin(self._breath_phase)
        self.update()

    # ------------------------------------------------------------------
    # 事件
    # ------------------------------------------------------------------
    def enterEvent(self, event: QEnterEvent) -> None:
        self._is_hovered = True
        if not self._is_active:
            self.setStyleSheet(
                "InstanceItemWidget { background: rgba(255,255,255,0.08);"
                " border: 1px solid transparent; border-radius: 8px; }"
            )
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._is_hovered = False
        self._update_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._meta.id)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        self.context_menu_requested.emit(self._meta.id, event.globalPos())

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 选中态：左侧 3px 强调条
        if self._is_active:
            color = QColor(self._meta.color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            rect = QRect(0, 8, 3, self.height() - 16)
            painter.drawRoundedRect(rect, 1, 1)

        # 右上角状态点：运行（蓝+呼吸）> 完成未读（绿）> 空闲（白）
        if self._task_running:
            r = 5
            x = self.width() - r - 6
            y = 6
            # 背景圈（半透明扩散）
            glow_r = int(r + 3 * self._breath_opacity)
            glow_color = QColor(self._DOT_COLOR_RUNNING)
            glow_color.setAlpha(int(80 * self._breath_opacity))
            painter.setBrush(glow_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPoint(x, y), glow_r, glow_r)
            # 主蓝点
            painter.setBrush(self._DOT_COLOR_RUNNING)
            painter.drawEllipse(QPoint(x, y), r, r)
        elif self._completed_unread:
            r = 5
            x = self.width() - r - 6
            y = 6
            painter.setBrush(self._DOT_COLOR_COMPLETED)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPoint(x, y), r, r)
        else:
            # 空闲：白色小点
            r = 4
            x = self.width() - r - 6
            y = 6
            painter.setBrush(self._DOT_COLOR_IDLE)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPoint(x, y), r, r)

        # 断线：右下角小叹号
        if not self._connected:
            r = 6
            x = self.width() - r - 4
            y = self.height() - r - 4
            painter.setBrush(QColor(138, 142, 164))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPoint(x, y), r, r)
            painter.setPen(QPen(QColor("white"), 1))
            font = painter.font()
            font.setPointSize(8)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRect(x - r, y - r, r * 2, r * 2), Qt.AlignmentFlag.AlignCenter, "!")


class InstanceSidebarWidget(QWidget):
    """最左侧的实例切换侧栏。"""

    FIXED_WIDTH = 72

    # 信号
    instance_activated = pyqtSignal(str)              # instance_id
    create_requested = pyqtSignal()
    rename_requested = pyqtSignal(str)                # instance_id
    recolor_requested = pyqtSignal(str)               # instance_id
    clone_requested = pyqtSignal(str)                 # instance_id
    delete_requested = pyqtSignal(str)                # instance_id
    open_in_explorer_requested = pyqtSignal(str)      # instance_id

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._logger = get_logger("instance.sidebar")
        self._items: dict[str, InstanceItemWidget] = {}
        self._active_id: Optional[str] = None

        self.setFixedWidth(self.FIXED_WIDTH)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "InstanceSidebarWidget { background: #14161c; border-right: 1px solid #23262e; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(6)

        # 顶部标题
        title = QLabel(locale.tr("instance_sidebar_title", "实例"))
        title.setStyleSheet(
            "color: #6b7280; font-size: 10px; background: transparent;"
            " font-weight: bold; padding: 0 0 4px 0;"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 实例列表容器
        self._list_container = QVBoxLayout()
        self._list_container.setSpacing(4)
        layout.addLayout(self._list_container, 1)

        # 底部固定区：新增按钮 + LLM 全局共享指示
        self._add_btn = self._build_add_button()
        layout.addWidget(self._add_btn)

        self._llm_indicator = QLabel("大模型")
        self._llm_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._llm_indicator.setStyleSheet(
            "color: #6b7280; font-size: 9px; background: transparent; padding: 4px 0;"
        )
        self._llm_indicator.setToolTip(locale.tr(
            "instance_llm_shared_tooltip",
            "大模型配置全局共享（本地 llama-server / 云端 API）",
        ))
        layout.addWidget(self._llm_indicator)

    def _build_add_button(self) -> QPushButton:
        btn = QPushButton("+", self)
        btn.setFixedSize(56, 36)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            "QPushButton { background: rgba(59,130,246,0.15); color: #3B82F6;"
            " border: 1px dashed #3B82F6; border-radius: 8px; font-size: 18px; font-weight: bold; }"
            "QPushButton:hover { background: rgba(59,130,246,0.25); }"
            "QPushButton:pressed { background: rgba(59,130,246,0.35); }"
        )
        btn.setToolTip(locale.tr("instance_add_tooltip", "新建实例"))
        btn.clicked.connect(self.create_requested.emit)
        return btn

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------
    def set_instances(self, metas: List[InstanceMeta]) -> None:
        """重置实例列表。"""
        # 清空旧 items
        for item in list(self._items.values()):
            item.setParent(None)
            item.deleteLater()
        self._items.clear()
        # 清空 layout
        while self._list_container.count():
            child = self._list_container.takeAt(0)
            if child.widget() is not None:
                child.widget().setParent(None)
        # 重建
        for meta in metas:
            item = InstanceItemWidget(meta, self)
            item.clicked.connect(self._on_item_clicked)
            item.context_menu_requested.connect(self._on_item_context_menu)
            self._list_container.addWidget(item)
            self._items[meta.id] = item
        self._list_container.addStretch()
        # 恢复选中态
        if self._active_id is not None and self._active_id in self._items:
            self._items[self._active_id].set_active(True)

    def set_active(self, instance_id: str) -> None:
        """设置当前活动实例。"""
        if self._active_id == instance_id:
            return
        # 取消旧选中
        if self._active_id is not None and self._active_id in self._items:
            self._items[self._active_id].set_active(False)
        self._active_id = instance_id
        if instance_id in self._items:
            self._items[instance_id].set_active(True)

    def set_task_running(self, instance_id: str, running: bool) -> None:
        item = self._items.get(instance_id)
        if item is not None:
            item.set_task_running(running)

    def set_completed_unread(self, instance_id: str, unread: bool) -> None:
        item = self._items.get(instance_id)
        if item is not None:
            item.set_completed_unread(unread)

    def set_connected(self, instance_id: str, connected: bool) -> None:
        item = self._items.get(instance_id)
        if item is not None:
            item.set_connected(connected)

    def update_meta(self, meta: InstanceMeta) -> None:
        """更新某个实例项的元数据（重命名/改色/改图标后调用）。"""
        item = self._items.get(meta.id)
        if item is not None:
            item.update_meta(meta)

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------
    def _on_item_clicked(self, instance_id: str) -> None:
        if instance_id == self._active_id:
            return
        self.instance_activated.emit(instance_id)

    def _on_item_context_menu(self, instance_id: str, global_pos: QPoint) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #1f2128; color: #d4d4d8; border: 1px solid #2d3038; }"
            "QMenu::item:selected { background: #2d3038; }"
        )

        is_default = instance_id == "default"

        act_switch = menu.addAction(locale.tr("instance_menu_switch", "切换到此实例"))
        menu.addSeparator()
        act_rename = menu.addAction(locale.tr("instance_menu_rename", "重命名"))
        act_recolor = menu.addAction(locale.tr("instance_menu_recolor", "修改颜色"))
        menu.addSeparator()
        act_clone = menu.addAction(locale.tr("instance_menu_clone", "克隆此实例"))
        act_open = menu.addAction(locale.tr("instance_menu_open_in_explorer", "在文件管理器中打开"))
        menu.addSeparator()
        act_delete = menu.addAction(locale.tr("instance_menu_delete", "删除"))
        if is_default:
            act_delete.setEnabled(False)
            act_delete.setToolTip(locale.tr("instance_menu_delete_disabled_tooltip", "default 实例不可删除"))

        action = menu.exec(global_pos)
        if action is None:
            return
        if action is act_switch:
            if instance_id != self._active_id:
                self.instance_activated.emit(instance_id)
        elif action is act_rename:
            self.rename_requested.emit(instance_id)
        elif action is act_recolor:
            self.recolor_requested.emit(instance_id)
        elif action is act_clone:
            self.clone_requested.emit(instance_id)
        elif action is act_open:
            self.open_in_explorer_requested.emit(instance_id)
        elif action is act_delete:
            self.delete_requested.emit(instance_id)


__all__ = ["InstanceSidebarWidget", "InstanceItemWidget"]
