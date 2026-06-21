"""
Endfield 工业科幻风格基础控件
Hypergryph 终末地设计语言：硬朗锐角 + 终端青蓝 + 工业暗面
"""

from typing import Optional
from PyQt6.QtWidgets import (
    QPushButton,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
)
from PyQt6.QtCore import Qt, pyqtProperty
from PyQt6.QtGui import QPainter

try:
    from ..theme.theme_manager import ThemeManager
    
except ImportError:
    from utils.paths import ensure_src_path
    ensure_src_path(__file__)
    
    from gui.pyqt6.theme.theme_manager import ThemeManager


class BaseButton(QPushButton):
    """
    Endfield 工业风格基础按钮
    硬朗锐角 + 终端青蓝光效
    """
    
    def __init__(
        self,
        text: str = "",
        parent: Optional[QWidget] = None,
        variant: str = "primary"
    ) -> None:
        super().__init__(text, parent)
        self._variant = variant
        self._theme = ThemeManager.get_instance()
        self._setup_style()
    
    def _setup_style(self) -> None:
        self.setProperty("variant", self._variant)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    
    @pyqtProperty(str)
    def variant(self) -> str:
        return self._variant
    
    def set_variant(self, variant: str) -> None:
        self._variant = variant
        self.setProperty("variant", variant)


class PrimaryButton(BaseButton):
    """Endfield 主要按钮（终端青蓝填充）"""
    
    def __init__(
        self,
        text: str = "",
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(text, parent, variant="primary")


class SecondaryButton(BaseButton):
    """Endfield 次级按钮（青蓝轮廓）"""
    
    def __init__(
        self,
        text: str = "",
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(text, parent, variant="secondary")


class TextButton(BaseButton):
    """Endfield 文本按钮（无背景）"""
    
    def __init__(
        self,
        text: str = "",
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(text, parent, variant="text")


class DangerButton(BaseButton):
    """Endfield 危险按钮（品红轮廓）"""
    
    def __init__(
        self,
        text: str = "",
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(text, parent, variant="danger")


class CardWidget(QWidget):
    """
    Endfield 工业暗面板卡
    硬朗锐角 + 微光边框
    """
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        title: Optional[str] = None,
        elevated: bool = False,
        outlined: bool = False
    ) -> None:
        super().__init__(parent)
        self._theme = ThemeManager.get_instance()
        self._title = title
        self._elevated = elevated
        self._outlined = outlined
        
        self._setup_ui()
        self._setup_style()
    
    def _setup_ui(self) -> None:
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(
            self._theme.get_spacing('card_padding'),
            self._theme.get_spacing('card_padding'),
            self._theme.get_spacing('card_padding'),
            self._theme.get_spacing('card_padding')
        )
        self._main_layout.setSpacing(self._theme.get_spacing('md'))
        
        if self._title:
            self._title_label = QLabel(self._title)
            self._title_label.setProperty("variant", "title")
            self._main_layout.addWidget(self._title_label)
        
        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(self._theme.get_spacing('sm'))
        self._main_layout.addWidget(self._content_widget)
    
    def _setup_style(self) -> None:
        if self._elevated:
            self.setProperty("class", "cardElevated")
        elif self._outlined:
            self.setProperty("class", "cardOutlined")
        else:
            self.setProperty("class", "card")
    
    def get_content_layout(self) -> QVBoxLayout:
        return self._content_layout
    
    def add_widget(self, widget: QWidget) -> None:
        self._content_layout.addWidget(widget)
    
    def add_layout(self, layout: QHBoxLayout | QVBoxLayout) -> None:
        self._content_layout.addLayout(layout)
    
    def set_title(self, title: str) -> None:
        self._title = title
        if hasattr(self, '_title_label') and self._title_label:
            self._title_label.setText(title)
        elif title:
            self._title_label = QLabel(title)
            self._title_label.setProperty("variant", "title")
            self._main_layout.insertWidget(0, self._title_label)


class ElevatedCardWidget(CardWidget):
    """Endfield 提升卡片"""
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        title: Optional[str] = None
    ) -> None:
        super().__init__(parent, title, elevated=True)


class OutlinedCardWidget(CardWidget):
    """Endfield 轮廓卡片"""
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        title: Optional[str] = None
    ) -> None:
        super().__init__(parent, title, outlined=True)


class NavigationButton(BaseButton):
    """
    Endfield 导航栏按钮
    左侧青蓝指示条 + 工业暗色
    """
    
    NAV_BUTTON_WIDTH = 200
    NAV_BUTTON_HEIGHT = 44
    
    def __init__(
        self,
        text: str = "",
        parent: Optional[QWidget] = None,
        icon: Optional[str] = None
    ) -> None:
        super().__init__(text, parent, variant="text")
        self._selected = False
        self._icon = icon
        self._setup_nav_style()
        
        self._anim_manager = None
        self._hover_animation = None
        self._click_animation = None
        
        self._base_bg_color = "transparent"
        self._hover_bg_color = "rgba(24, 209, 255, 0.08)"
        self._pressed_bg_color = "rgba(24, 209, 255, 0.20)"
        self._selected_bg_color = "rgba(24, 209, 255, 0.10)"
        self._is_hovered = False
        self._is_pressed = False
        
        self.setFixedSize(self.NAV_BUTTON_WIDTH, self.NAV_BUTTON_HEIGHT)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
    
    def _setup_nav_style(self) -> None:
        self.setProperty("class", "navButton")
    
    @pyqtProperty(bool)
    def selected(self) -> bool:
        return self._selected
    
    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.setProperty("selected", "true" if selected else "false")
        
        if selected:
            self._update_style_with_bg(self._selected_bg_color)
        else:
            self._update_style_with_bg(self._base_bg_color)
        
        if selected and self._anim_manager and self._anim_manager.is_enabled():
            self._pulse_animation()
    
    def toggle_selected(self) -> None:
        self.set_selected(not self._selected)
    
    def enterEvent(self, event):
        super().enterEvent(event)
        self._is_hovered = True
        if self._anim_manager and self._anim_manager.is_enabled() and self._anim_manager._config.hover_enabled:
            self._start_hover_animation(True)
    
    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._is_hovered = False
        if self._anim_manager and self._anim_manager.is_enabled() and self._anim_manager._config.hover_enabled:
            self._start_hover_animation(False)
    
    def _start_hover_animation(self, entering: bool) -> None:
        if self._hover_animation:
            self._hover_animation.stop()
        
        if entering:
            bg_color = self._selected_bg_color if self._selected else self._hover_bg_color
        else:
            bg_color = self._selected_bg_color if self._selected else self._base_bg_color
        
        self._update_style_with_bg(bg_color)

    def _update_style_with_bg(self, bg_color: str) -> None:
        selected_border = "2px solid #18d1ff" if self._selected else "none"
        text_color = "#e8e8ee" if self._selected else "#9090a8"
        obj_name = self.objectName() or "navButton"
        style = (
            "QPushButton#" + obj_name + " {"
            "background-color: " + bg_color + ";"
            "border: none;"
            "border-left: " + selected_border + ";"
            "border-radius: 0px;"
            "padding: 10px 20px;"
            "text-align: left;"
            "color: " + text_color + ";"
            "font-size: 14px;"
            "}"
            "QPushButton#" + obj_name + ":hover {"
            "background-color: " + self._hover_bg_color + ";"
            "}"
            "QPushButton#" + obj_name + ":pressed {"
            "background-color: " + self._pressed_bg_color + ";"
            "}"
        )
        self.setStyleSheet(style)
    
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self._is_pressed = True
        if self._anim_manager and self._anim_manager.is_enabled():
            self._start_click_animation()
    
    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self._is_pressed = False
        if self._anim_manager and self._anim_manager.is_enabled():
            self._restore_from_click()
    
    def _start_click_animation(self) -> None:
        self._update_style_with_bg(self._pressed_bg_color)
    
    def _restore_from_click(self) -> None:
        if self._selected:
            bg_color = self._selected_bg_color
        elif self._is_hovered:
            bg_color = self._hover_bg_color
        else:
            bg_color = self._base_bg_color
        
        self._update_style_with_bg(bg_color)
    
    def _pulse_animation(self) -> None:
        from PyQt6.QtCore import QTimer

        pulse_color = "rgba(24, 209, 255, 0.20)"
        self._update_style_with_bg(pulse_color)

        if self._anim_manager:
            QTimer.singleShot(self._anim_manager._config.duration_fast,
                              lambda: self._update_style_with_bg(self._selected_bg_color))


class HorizontalSeparator(QFrame):
    """水平分割线 - 青蓝微光"""
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFrameShadow(QFrame.Shadow.Plain)
        self.setFixedHeight(1)


class VerticalSeparator(QFrame):
    """垂直分割线"""
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.VLine)
        self.setFrameShadow(QFrame.Shadow.Plain)
        self.setFixedWidth(1)