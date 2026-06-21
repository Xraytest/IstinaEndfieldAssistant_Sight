"""
Endfield 风格主题管理器
基于 Hypergryph 终末地工业科幻设计语言 + 明日方舟终端命令行美学
"""

from typing import Dict, Optional, Any
from PyQt6.QtWidgets import QApplication


# ============================================================================
# 颜色定义 - Endfield 工业科幻 + Arknights 终端混合设计
# ============================================================================

COLORS: Dict[str, str] = {
    # === 主色调 - 终端青蓝 ===
    'primary': '#18d1ff',
    'primary_hover': '#3ddbff',
    'primary_light': '#6ae5ff',
    'primary_lighter': '#a3f0ff',
    'primary_light_container': 'rgba(24, 209, 255, 0.12)',
    'primary_dark': '#06bbff',
    'primary_darker': '#0099cc',
    'primary_dark_container': 'rgba(0, 153, 204, 0.25)',
    'on_primary': '#000000',
    'on_primary_container': '#c0f0ff',

    # === 金色/琥珀色高亮 (终端警告/重要信息) ===
    'accent_gold': '#fffa00',
    'accent_gold_light': '#fffb4d',
    'accent_gold_dark': '#e6de01',
    'accent_gold_glow': 'rgba(255, 250, 0, 0.2)',

    # === 次级色 - 品红(Endfield 特色) ===
    'secondary': '#ff1aac',
    'secondary_light': '#ff4dc0',
    'secondary_dark': '#cc0088',
    'secondary_container': 'rgba(255, 26, 172, 0.12)',
    'on_secondary': '#000000',
    'on_secondary_container': '#ffccee',

    # === 第三色 - 终端绿 ===
    'tertiary': '#00ffa2',
    'tertiary_light': '#4dffbc',
    'tertiary_dark': '#00cc81',
    'tertiary_container': 'rgba(0, 255, 162, 0.12)',
    'on_tertiary': '#000000',
    'on_tertiary_container': '#ccffee',

    # === 语义颜色 ===
    'success': '#00ffa2',
    'success_light': '#4dffbc',
    'success_dark': '#00cc81',
    'success_container': 'rgba(0, 255, 162, 0.12)',
    'on_success': '#000000',

    'warning': '#fffa00',
    'warning_light': '#fffb4d',
    'warning_dark': '#e6de01',
    'warning_container': 'rgba(255, 250, 0, 0.12)',
    'on_warning': '#000000',

    'danger': '#ff3355',
    'danger_light': '#ff6680',
    'danger_dark': '#cc0022',
    'danger_container': 'rgba(255, 51, 85, 0.12)',
    'on_danger': '#ffffff',

    'info': '#18d1ff',
    'info_light': '#6ae5ff',
    'info_dark': '#0099cc',
    'info_container': 'rgba(24, 209, 255, 0.12)',
    'on_info': '#000000',

    # === 深色主题背景 - 工业暗黑(Endfield 色板) ===
    'bg_primary': '#0a0a0f',
    'bg_secondary': '#101016',
    'bg_tertiary': '#14141a',
    'bg_card': 'rgba(18, 18, 26, 0.92)',
    'bg_elevated': 'rgba(26, 26, 38, 0.90)',
    'surface': '#0a0a0f',
    'surface_dim': '#07070b',
    'surface_bright': 'rgba(30, 30, 45, 0.85)',
    'surface_container_lowest': '#050508',
    'surface_container_low': 'rgba(12, 12, 20, 0.93)',
    'surface_container': 'rgba(16, 16, 26, 0.88)',
    'surface_container_high': 'rgba(22, 22, 36, 0.85)',
    'surface_container_highest': 'rgba(28, 28, 46, 0.82)',
    'on_surface': '#e8e8ee',
    'on_surface_variant': '#9090a8',

    # === 文字颜色 ===
    'text_primary': '#e8e8ee',
    'text_secondary': '#9090a8',
    'text_tertiary': '#606080',
    'text_muted': '#404058',
    'text_disabled': '#282840',

    # === 边框和分割线 - CRT 扫描线微光 ===
    'border_color': 'rgba(24, 209, 255, 0.15)',
    'border_light': 'rgba(24, 209, 255, 0.08)',
    'border_glow': 'rgba(255, 250, 0, 0.08)',
    'divider_color': 'rgba(24, 209, 255, 0.10)',
    'outline': 'rgba(24, 209, 255, 0.20)',
    'outline_variant': 'rgba(24, 209, 255, 0.12)',

    # === 特殊用途 ===
    'canvas_bg': '#050508',
    'log_bg': 'rgba(5, 5, 8, 0.95)',
    'selection_bg': 'rgba(24, 209, 255, 0.25)',
    'selection_border': '#18d1ff',
    'hover_bg': 'rgba(24, 209, 255, 0.08)',
    'inverse_surface': '#e0e0e8',
    'inverse_on_surface': '#0a0a0f',
    'inverse_primary': '#0099cc',

    # === 阴影颜色 ===
    'shadow': 'rgba(0, 0, 0, 0.5)',
    'shadow_light': 'rgba(0, 0, 0, 0.3)',
    'shadow_cyan': 'rgba(24, 209, 255, 0.06)',
}

# 用户层级颜色
TIER_COLORS: Dict[str, str] = {
    'free': COLORS['text_muted'],
    'prime': COLORS['primary'],
    'plus': COLORS['accent_gold'],
    'pro': COLORS['secondary'],
}


# ============================================================================
# 字体定义 - 终端等宽 + 工业无衬线
# ============================================================================

FONTS: Dict[str, str] = {
    'family': 'Microsoft YaHei UI',
    'family_fallback': 'Segoe UI',
    'family_mono': 'Consolas',
    'family_display': 'Microsoft YaHei UI',
}

FONT_SIZES: Dict[str, int] = {
    'display_large': 42,
    'display_medium': 34,
    'display_small': 26,
    'headline_large': 24,
    'headline_medium': 20,
    'headline_small': 17,
    'title_large': 15,
    'title_medium': 13,
    'title_small': 12,
    'body_large': 13,
    'body_medium': 12,
    'body_small': 11,
    'label_large': 12,
    'label_medium': 11,
    'label_small': 10,
    'size_small': 11,
    'size_base': 12,
    'size_medium': 12,
    'size_large': 13,
    'size_xlarge': 15,
    'size_title': 17,
    'size_header': 20,
}

FONT_WEIGHTS: Dict[str, int] = {
    'thin': 100,
    'extra_light': 200,
    'light': 300,
    'regular': 400,
    'medium': 500,
    'semi_bold': 600,
    'bold': 700,
    'extra_bold': 800,
    'black': 900,
}


# ============================================================================
# 间距定义 - 紧凑工业风
# ============================================================================

SPACING_UNIT = 4

SPACING: Dict[str, int] = {
    'none': 0,
    'xxxs': 2,
    'xxs': 4,
    'xs': 6,
    'sm': 8,
    'md': 12,
    'lg': 16,
    'xl': 20,
    'xxl': 24,
    'xxxl': 32,
    'component': 8,
    'section': 16,
    'container': 20,
    'padding_xs': 4,
    'padding_sm': 8,
    'padding_md': 12,
    'padding_lg': 16,
    'padding_xl': 20,
    'margin_xs': 4,
    'margin_sm': 8,
    'margin_md': 12,
    'margin_lg': 16,
    'margin_xl': 20,
    'icon_text': 8,
    'button_padding_h': 24,
    'button_padding_v': 10,
    'input_padding_h': 14,
    'input_padding_v': 10,
    'card_padding': 20,
    'list_item_padding': 10,
    'dialog_padding': 24,
}


# ============================================================================
# 圆角定义 - 硬朗工业锐角为主
# ============================================================================

CORNER_RADIUS: Dict[str, int] = {
    'none': 0,
    'xs': 2,
    'sm': 4,
    'md': 6,
    'lg': 8,
    'xl': 12,
    'xxl': 16,
    'full': 9999,
    'button': 4,
    'button_sm': 4,
    'button_lg': 6,
    'card': 6,
    'card_lg': 8,
    'input': 4,
    'input_outlined': 4,
    'input_filled': 4,
    'dialog': 8,
    'chip': 4,
    'badge': 9999,
    'fab': 8,
    'menu': 4,
    'tooltip': 3,
    'snackbar': 4,
}


# ============================================================================
# 阴影定义
# ============================================================================

ELEVATION: Dict[str, int] = {
    'level_0': 0,
    'level_1': 1,
    'level_2': 2,
    'level_3': 3,
    'level_4': 4,
    'level_5': 5,
    'card': 1,
    'card_hover': 2,
    'button': 0,
    'button_floating': 3,
    'menu': 2,
    'dialog': 3,
    'drawer': 4,
    'modal': 5,
}


# ============================================================================
# 动画时间定义
# ============================================================================

DURATION: Dict[str, int] = {
    'instant': 0,
    'fast': 100,
    'normal': 180,
    'slow': 300,
    'slower': 400,
    'hover': 120,
    'press': 60,
    'fade': 180,
    'slide': 250,
    'expand': 200,
    'dialog': 250,
    'snackbar': 200,
}


# ============================================================================
# 动画配置
# ============================================================================

ANIMATION_CONFIG: Dict[str, Any] = {
    'enabled': True,
    'duration_fast': 120,
    'duration_normal': 200,
    'duration_slow': 350,
    'easing_curve': 'OutCubic',
    'fade_enabled': True,
    'slide_enabled': True,
    'scale_enabled': True,
    'hover_enabled': True,
}


class ThemeManager:
    """
    Endfield 工业科幻风格主题管理器

    基于 Hypergryph 终末地设计语言 + 明日方舟终端命令行美学:
    - 暗夜工业黑背景 (#0a0a0f)
    - 终端青蓝 (#18d1ff) 主色调
    - 品红 (#ff1aac) + 终端绿 (#00ffa2) 辅色
    - CRT 扫描线微光边框
    - 硬朗简洁的工业锐角
    """

    _instance: Optional['ThemeManager'] = None

    def __new__(cls) -> 'ThemeManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, '_initialized') and self._initialized:
            return
        self._initialized = True
        self._colors = COLORS
        self._fonts = FONTS
        self._font_sizes = FONT_SIZES
        self._font_weights = FONT_WEIGHTS
        self._spacing = SPACING
        self._corner_radius = CORNER_RADIUS
        self._elevation = ELEVATION
        self._duration = DURATION
        self._animation_config = ANIMATION_CONFIG.copy()
    
    # === 属性访问器 ===
    
    @property
    def colors(self) -> Dict[str, str]:
        return self._colors
    
    @property
    def fonts(self) -> Dict[str, str]:
        return self._fonts
    
    @property
    def font_sizes(self) -> Dict[str, int]:
        return self._font_sizes
    
    @property
    def font_weights(self) -> Dict[str, int]:
        return self._font_weights
    
    @property
    def spacing(self) -> Dict[str, int]:
        return self._spacing
    
    @property
    def corner_radius(self) -> Dict[str, int]:
        return self._corner_radius
    
    @property
    def elevation(self) -> Dict[str, int]:
        return self._elevation
    
    @property
    def duration(self) -> Dict[str, int]:
        return self._duration
    
    @property
    def animation_config(self) -> Dict[str, Any]:
        return self._animation_config
    
    # === 动画配置方法 ===
    
    def is_animation_enabled(self) -> bool:
        return self._animation_config.get('enabled', True)
    
    def set_animation_enabled(self, enabled: bool) -> None:
        self._animation_config['enabled'] = enabled
    
    def get_animation_duration(self, key: str = 'normal') -> int:
        duration_key = f'duration_{key}'
        return self._animation_config.get(duration_key, self._duration.get(key, 250))
    
    def set_animation_duration(self, key: str, duration: int) -> None:
        self._animation_config[f'duration_{key}'] = duration
    
    # === 便捷访问方法 ===
    
    def get_color(self, key: str) -> str:
        return self._colors.get(key, '#000000')
    
    def get_font_size(self, key: str) -> int:
        return self._font_sizes.get(key, 12)
    
    def get_spacing(self, key: str) -> int:
        return self._spacing.get(key, 0)
    
    def get_corner_radius(self, key: str) -> int:
        return self._corner_radius.get(key, 0)
    
    def get_font_family(self) -> str:
        return self._fonts['family']
    
    def get_mono_font_family(self) -> str:
        return self._fonts['family_mono']
    
    # === QSS 样式生成 ===
    
    def get_stylesheet(self) -> str:
        try:
            return self._build_stylesheet()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"构建样式表失败: {e}")
            return ""

    def _build_stylesheet(self) -> str:
        c = self._colors
        f = self._fonts
        fs = self._font_sizes
        s = self._spacing
        r = self._corner_radius

        stylesheet = """
/* ============================================================================
 * Endfield 工业科幻风格 - PyQt6 QSS 样式表
 * 暗夜工业黑 + 终端青蓝主色 + CRT 微光边框
 * ============================================================================ */

/* === 全局样式 === */
QWidget {
    font-family: '%s';
    font-size: %dpx;
    color: %s;
    background-color: %s;
}

QMainWindow {
    background-color: %s;
}

/* === 按钮样式 - 硬朗工业风 === */
QPushButton {
    background-color: %s;
    color: %s;
    border: 1px solid %s;
    border-radius: %dpx;
    padding: %dpx %dpx;
    font-size: %dpx;
    font-weight: %d;
    min-height: 36px;
}

QPushButton:hover {
    background-color: %s;
    border-color: %s;
}

QPushButton:pressed {
    background-color: %s;
    border-color: %s;
}

QPushButton:disabled {
    background-color: %s;
    color: %s;
    border-color: %s;
}

/* 主要按钮 - 终端青蓝 */
QPushButton[variant="primary"] {
    background-color: %s;
    color: %s;
    border: 1px solid %s;
}

QPushButton[variant="primary"]:hover {
    background-color: %s;
}

QPushButton[variant="primary"]:pressed {
    background-color: %s;
}

/* 次级按钮 - 透明青蓝轮廓 */
QPushButton[variant="secondary"] {
    background-color: transparent;
    color: %s;
    border: 1px solid %s;
}

QPushButton[variant="secondary"]:hover {
    background-color: %s;
    border-color: %s;
}

/* 文本按钮 */
QPushButton[variant="text"] {
    background-color: transparent;
    color: %s;
    border: none;
}

QPushButton[variant="text"]:hover {
    background-color: %s;
}

/* 危险按钮 */
QPushButton[variant="danger"] {
    background-color: transparent;
    color: %s;
    border: 1px solid %s;
}

QPushButton[variant="danger"]:hover {
    background-color: %s;
    border-color: %s;
}

/* === 标签样式 === */
QLabel {
    color: %s;
    background-color: transparent;
    border: none;
}

QLabel[variant="header"] {
    font-size: %dpx;
    font-weight: %d;
    color: %s;
}

QLabel[variant="title"] {
    font-size: %dpx;
    font-weight: %d;
    color: %s;
}

QLabel[variant="secondary"] {
    color: %s;
}

QLabel[variant="muted"] {
    color: %s;
}

QLabel[variant="terminal"] {
    font-family: '%s';
    color: %s;
    font-size: %dpx;
}

QLabel[variant="accent"] {
    color: %s;
}

QLabel[variant="success"] {
    color: %s;
}

QLabel[variant="danger"] {
    color: %s;
}

/* === 输入框样式 - 终端暗色 === */
QLineEdit {
    background-color: %s;
    color: %s;
    border: 1px solid %s;
    border-radius: %dpx;
    padding: %dpx %dpx;
    font-size: %dpx;
    min-height: 36px;
}

QLineEdit:hover {
    border-color: %s;
}

QLineEdit:focus {
    border-color: %s;
    border-width: 1px;
}

QLineEdit:disabled {
    background-color: %s;
    color: %s;
}

/* === 下拉框 === */
QComboBox {
    background-color: %s;
    color: %s;
    border: 1px solid %s;
    border-radius: %dpx;
    padding: %dpx %dpx;
    font-size: %dpx;
    min-height: 36px;
}

QComboBox:hover {
    border-color: %s;
}

QComboBox:focus {
    border-color: %s;
}

QComboBox::drop-down {
    border: none;
    width: 28px;
    padding-right: 8px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid %s;
    width: 0;
    height: 0;
}

QComboBox QAbstractItemView {
    background-color: %s;
    color: %s;
    border: 1px solid %s;
    border-radius: %dpx;
    selection-background-color: %s;
    selection-color: %s;
    padding: 4px;
}

/* === 数值调节框 === */
QSpinBox {
    background-color: %s;
    color: %s;
    border: 1px solid %s;
    border-radius: %dpx;
    padding: %dpx %dpx;
    font-size: %dpx;
    min-height: 36px;
}

QSpinBox:hover {
    border-color: %s;
}

QSpinBox:focus {
    border-color: %s;
}

QSpinBox::up-button, QSpinBox::down-button {
    background-color: %s;
    border: none;
    width: 24px;
    subcontrol-position: right;
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: %s;
}

QSpinBox::up-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-bottom: 6px solid %s;
    width: 0;
    height: 0;
}

QSpinBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid %s;
    width: 0;
    height: 0;
}

/* === 复选框 === */
QCheckBox {
    color: %s;
    spacing: %dpx;
    font-size: %dpx;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 3px;
    border: 1px solid %s;
    background-color: transparent;
}

QCheckBox::indicator:hover {
    border-color: %s;
}

QCheckBox::indicator:checked {
    background-color: %s;
    border-color: %s;
}

QCheckBox::indicator:disabled {
    border-color: %s;
    background-color: %s;
}

/* === 标签页 === */
QTabWidget::pane {
    background-color: %s;
    border: 1px solid %s;
    border-radius: %dpx;
    top: -1px;
}

QTabBar::tab {
    background-color: transparent;
    color: %s;
    border: none;
    border-bottom: 2px solid transparent;
    padding: %dpx %dpx;
    font-size: %dpx;
    min-width: 80px;
}

QTabBar::tab:hover {
    background-color: %s;
}

QTabBar::tab:selected {
    color: %s;
    border-bottom: 2px solid %s;
}

/* === 分割器 === */
QSplitter::handle {
    background-color: %s;
}

QSplitter::handle:horizontal {
    width: 1px;
}

QSplitter::handle:vertical {
    height: 1px;
}

/* === 滚动条 - CRT 暗色细条 === */
QScrollBar:vertical {
    background-color: transparent;
    width: 6px;
    border-radius: 3px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: %s;
    border-radius: 3px;
    min-height: 32px;
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background-color: %s;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
    background-color: transparent;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background-color: transparent;
}

QScrollBar:horizontal {
    background-color: transparent;
    height: 6px;
    border-radius: 3px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background-color: %s;
    border-radius: 3px;
    min-width: 32px;
    margin: 2px;
}

QScrollBar::handle:horizontal:hover {
    background-color: %s;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
    background-color: transparent;
}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background-color: transparent;
}

/* === 列表视图 === */
QListWidget {
    background-color: %s;
    color: %s;
    border: 1px solid %s;
    border-radius: %dpx;
    padding: %dpx;
    font-size: %dpx;
}

QListWidget::item {
    background-color: transparent;
    padding: %dpx;
    border-radius: %dpx;
}

QListWidget::item:hover {
    background-color: %s;
}

QListWidget::item:selected {
    background-color: %s;
    color: %s;
    border: 1px solid %s;
}

QListWidget::item:selected:!active {
    background-color: %s;
}

/* === 表格视图 === */
QTableWidget, QTableView {
    background-color: %s;
    color: %s;
    border: 1px solid %s;
    border-radius: %dpx;
    gridline-color: %s;
    font-size: %dpx;
}

QTableWidget::item, QTableView::item {
    padding: %dpx;
    border: none;
}

QTableWidget::item:hover, QTableView::item:hover {
    background-color: %s;
}

QTableWidget::item:selected, QTableView::item:selected {
    background-color: %s;
    color: %s;
}

QHeaderView::section {
    background-color: %s;
    color: %s;
    border: none;
    border-bottom: 1px solid %s;
    padding: %dpx;
    font-size: %dpx;
    font-weight: %d;
}

/* === 树形视图 === */
QTreeWidget, QTreeView {
    background-color: %s;
    color: %s;
    border: 1px solid %s;
    border-radius: %dpx;
    font-size: %dpx;
}

QTreeWidget::item, QTreeView::item {
    padding: %dpx;
    border-radius: %dpx;
}

QTreeWidget::item:hover, QTreeView::item:hover {
    background-color: %s;
}

QTreeWidget::item:selected, QTreeView::item:selected {
    background-color: %s;
    color: %s;
}

/* === 分组框 === */
QGroupBox {
    background-color: %s;
    color: %s;
    border: 1px solid %s;
    border-radius: %dpx;
    font-size: %dpx;
    padding-top: %dpx;
    margin-top: 12px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: %dpx;
    padding: 0 %dpx;
    color: %s;
    font-weight: %d;
}

/* === 进度条 === */
QProgressBar {
    background-color: %s;
    border: none;
    border-radius: %dpx;
    height: 4px;
    text-align: center;
    color: %s;
}

QProgressBar::chunk {
    background-color: %s;
    border-radius: %dpx;
}

/* === 文本编辑框 === */
QTextEdit, QPlainTextEdit {
    background-color: %s;
    color: %s;
    border: 1px solid %s;
    border-radius: %dpx;
    padding: %dpx;
    font-size: %dpx;
    font-family: '%s';
}

QTextEdit:focus, QPlainTextEdit:focus {
    border-color: %s;
}

/* === 菜单 === */
QMenu {
    background-color: %s;
    color: %s;
    border: 1px solid %s;
    border-radius: %dpx;
    padding: 4px;
}

QMenu::item {
    padding: %dpx %dpx;
    border-radius: %dpx;
}

QMenu::item:selected {
    background-color: %s;
}

QMenu::separator {
    height: 1px;
    background-color: %s;
    margin: 4px 8px;
}

/* === 工具提示 === */
QToolTip {
    background-color: %s;
    color: %s;
    border: 1px solid %s;
    border-radius: %dpx;
    padding: %dpx %dpx;
    font-size: %dpx;
}

/* === 对话框 === */
QDialog {
    background-color: %s;
    border: 1px solid %s;
}

/* === 卡片容器 - 工业暗色面板 === */
QWidget[class="card"] {
    background-color: %s;
    border: 1px solid %s;
    border-radius: %dpx;
    padding: %dpx;
}

QWidget[class="card"] > QWidget {
    background-color: transparent;
}

QWidget[class="card"]:hover {
    border-color: %s;
}

QWidget[class="cardElevated"] {
    background-color: %s;
    border: 1px solid %s;
    border-radius: %dpx;
    padding: %dpx;
}

QWidget[class="cardElevated"] > QWidget {
    background-color: transparent;
}

QWidget[class="cardOutlined"] {
    background-color: %s;
    border: 1px solid %s;
    border-radius: %dpx;
    padding: %dpx;
}

QWidget[class="cardOutlined"] > QWidget {
    background-color: transparent;
}

/* === 内容区域 === */
QWidget[class="contentArea"] {
    background-color: %s;
}

/* === 导航栏 - 终端暗色面板 === */
QWidget[class="navigationBar"] {
    background-color: %s;
    border-right: 1px solid %s;
}

QPushButton[class="navButton"] {
    background-color: transparent;
    color: %s;
    border: none;
    border-left: 2px solid transparent;
    border-radius: 0px;
    padding: %dpx %dpx;
    text-align: left;
    min-height: 42px;
    font-size: %dpx;
}

QPushButton[class="navButton"]:hover {
    background-color: %s;
}

QPushButton[class="navButton"]:checked, QPushButton[class="navButton"][selected="true"] {
    background-color: rgba(24, 209, 255, 0.10);
    color: %s;
    border-left: 2px solid %s;
}

/* === 状态栏 === */
QStatusBar {
    background-color: %s;
    color: %s;
    border-top: 1px solid %s;
    font-size: %dpx;
}

QStatusBar::item {
    border: none;
}

/* === 堆叠控件 === */
QStackedWidget {
    background-color: %s;
}

QStackedWidget > QWidget {
    background-color: %s;
}

/* === 滚动区域 === */
QScrollArea {
    background-color: %s;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background-color: %s;
}

/* === 分割线 === */
QFrame[frameShape="4"] {
    background-color: %s;
    max-height: 1px;
    border: none;
}

QFrame[frameShape="5"] {
    background-color: %s;
    max-width: 1px;
    border: none;
}
""" % (
            # 全局样式
            f['family'], fs['size_base'], c['text_primary'], c['surface'],
            c['surface'],

            # 按钮样式
            c['surface_container'], c['text_primary'], c['outline_variant'],
            r['button_sm'], s['button_padding_v'], s['button_padding_h'],
            fs['label_large'], FONT_WEIGHTS['medium'],
            c['hover_bg'], c['outline'],
            c['surface_container_high'], c['outline'],
            c['surface_container_high'], c['text_disabled'], c['outline_variant'],

            # 主要按钮
            c['primary'], c['on_primary'], c['primary'],
            c['primary_hover'],
            c['primary_dark'],

            # 次级按钮
            c['text_primary'], c['outline'],
            c['hover_bg'], c['primary'],

            # 文本按钮
            c['text_secondary'],
            c['hover_bg'],

            # 危险按钮
            c['danger'], c['danger'],
            c['danger_container'], c['danger_light'],

            # 标签样式
            c['text_primary'],
            fs['size_header'], FONT_WEIGHTS['semi_bold'], c['text_primary'],
            fs['size_title'], FONT_WEIGHTS['semi_bold'], c['text_primary'],
            c['text_secondary'],
            c['text_muted'],
            f['family_mono'], c['primary'], fs['size_base'],
            c['accent_gold'],
            c['tertiary'],
            c['danger'],

            # 输入框样式
            c['surface_container'], c['text_primary'], c['outline_variant'],
            r['input'], s['input_padding_v'], s['input_padding_h'], fs['size_base'],
            c['outline'],
            c['primary'],
            c['surface_container_high'], c['text_disabled'],

            # 下拉框样式
            c['surface_container'], c['text_primary'], c['outline_variant'],
            r['input'], s['input_padding_v'], s['input_padding_h'], fs['size_base'],
            c['outline'],
            c['primary'],
            c['text_secondary'],
            c['surface_container'], c['text_primary'], c['outline_variant'],
            r['sm'], c['selection_bg'], c['on_primary'],

            # 数值调节框样式
            c['surface_container'], c['text_primary'], c['outline_variant'],
            r['input'], s['input_padding_v'], s['input_padding_h'], fs['size_base'],
            c['outline'],
            c['primary'],
            c['canvas_bg'],
            c['hover_bg'],
            c['text_primary'],
            c['text_primary'],

            # 复选框样式
            c['text_primary'], s['icon_text'], fs['size_base'],
            c['outline'],
            c['primary'],
            c['primary'], c['primary'],
            c['text_disabled'], c['surface_container'],

            # 标签页样式
            c['surface'], c['outline_variant'], r['sm'],
            c['text_secondary'],
            s['padding_sm'], s['padding_xl'], fs['label_large'],
            c['hover_bg'],
            c['primary'], c['primary'],

            # 分割器样式
            c['divider_color'],

            # 滚动条样式 - 垂直
            c['outline_variant'],
            c['outline'],

            # 滚动条样式 - 水平
            c['outline_variant'],
            c['outline'],

            # 列表视图样式
            c['surface'], c['text_primary'], c['outline_variant'],
            r['sm'], s['padding_sm'], fs['size_base'],
            s['list_item_padding'], r['xs'],
            c['hover_bg'],
            c['selection_bg'], c['on_primary'], c['selection_border'],
            c['primary_light_container'],

            # 表格视图样式
            c['surface'], c['text_primary'], c['outline_variant'],
            r['sm'], c['divider_color'], fs['size_base'],
            s['padding_sm'],
            c['hover_bg'],
            c['selection_bg'], c['on_primary'],
            c['surface_container'], c['text_primary'], c['outline_variant'],
            s['padding_sm'], fs['label_large'], FONT_WEIGHTS['medium'],

            # 树形视图样式
            c['surface'], c['text_primary'], c['outline_variant'],
            r['sm'], fs['size_base'],
            s['list_item_padding'], r['xs'],
            c['hover_bg'],
            c['selection_bg'], c['on_primary'],

            # 分组框样式
            c['surface_container_low'], c['text_primary'], c['outline_variant'],
            r['sm'], fs['size_base'], s['padding_xl'],
            s['padding_sm'], s['padding_sm'], c['text_secondary'], FONT_WEIGHTS['medium'],

            # 进度条样式
            c['surface_container'], r['full'], c['text_primary'],
            c['primary'], r['full'],

            # 文本编辑框样式
            c['log_bg'], c['text_primary'], c['outline_variant'],
            r['sm'], s['padding_sm'], fs['size_base'], f['family_mono'],
            c['primary'],

            # 菜单样式
            c['surface_container'], c['text_primary'], c['outline_variant'],
            r['menu'],
            s['padding_sm'], s['padding_xl'], r['xs'],
            c['hover_bg'],
            c['divider_color'],

            # 工具提示样式
            c['surface_bright'], c['text_primary'], c['outline_variant'],
            r['tooltip'], s['padding_sm'], s['padding_md'], fs['label_medium'],

            # 对话框样式
            c['surface'], c['outline_variant'],

            # 卡片容器样式
            c['bg_card'], c['outline_variant'],
            r['card'], s['card_padding'],
            c['border_glow'],
            c['bg_elevated'], c['border_light'],
            r['card_lg'], s['card_padding'],
            c['bg_card'], c['outline_variant'],
            r['card'], s['card_padding'],

            # 内容区域样式
            c['surface'],

            # 导航栏样式
            c['surface_dim'], c['outline_variant'],
            c['text_secondary'],
            s['padding_md'], s['padding_lg'], fs['size_base'],
            c['hover_bg'],
            c['text_primary'], c['primary'],

            # 状态栏样式
            c['surface_dim'], c['text_secondary'], c['outline_variant'],
            fs['label_medium'],

            # 堆叠控件样式
            c['surface'],
            c['surface'],

            # 滚动区域样式
            c['surface'],
            c['surface'],

            # 分割线样式
            c['divider_color'],
            c['divider_color'],
        )

        return stylesheet
    
    def apply_theme(self, app: QApplication) -> None:
        try:
            stylesheet = self.get_stylesheet()
            app.setStyleSheet(stylesheet)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"应用主题失败: {e}")
            app.setStyleSheet("")

    @classmethod
    def get_instance(cls) -> 'ThemeManager':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


def get_theme() -> ThemeManager:
    return ThemeManager.get_instance()


def apply_theme(app: QApplication) -> None:
    ThemeManager.get_instance().apply_theme(app)


def get_stylesheet() -> str:
    return ThemeManager.get_instance().get_stylesheet()