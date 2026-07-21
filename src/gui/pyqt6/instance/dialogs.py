"""实例管理对话框（新建/重命名/改色/删除确认）。"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.pyqt6.i18n import get_locale_manager
from .registry import PRESET_COLORS, InstanceMeta


locale = get_locale_manager()


class NewInstanceDialog(QDialog):
    """新建实例对话框。

    收集：display_name / color / clone_from
    """

    def __init__(self, existing_metas: list, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(locale.tr("instance_new_dialog_title", "新建实例"))
        self.setMinimumWidth(360)
        self._existing_metas = existing_metas
        self._selected_color = PRESET_COLORS[0]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        # 显示名
        layout.addWidget(QLabel(locale.tr("instance_new_name", "实例名称:")))
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText(locale.tr(
            "instance_new_name_placeholder", "如：账号2"
        ))
        layout.addWidget(self._name_edit)

        # 颜色
        layout.addWidget(QLabel(locale.tr("instance_new_color", "主题色:")))
        color_row = QHBoxLayout()
        self._color_buttons: list[QPushButton] = []
        for c in PRESET_COLORS:
            btn = QPushButton()
            btn.setFixedSize(24, 24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"background: {c}; border-radius: 12px; border: 2px solid transparent;"
            )
            btn.clicked.connect(lambda _, color=c: self._on_color_selected(color))
            color_row.addWidget(btn)
            self._color_buttons.append((c, btn))
        color_row.addStretch()
        layout.addLayout(color_row)

        # 克隆来源
        layout.addWidget(QLabel(locale.tr("instance_new_clone_from", "克隆自（可选）:")))
        from PyQt6.QtWidgets import QComboBox
        self._clone_combo = QComboBox()
        self._clone_combo.addItem(locale.tr("instance_new_clone_none", "（不克隆，使用空配置）"), None)
        for m in existing_metas:
            label = f"{m.display_name} ({m.id})"
            self._clone_combo.addItem(label, m.id)
        layout.addWidget(self._clone_combo)

        # 提示
        tip = QLabel(locale.tr(
            "instance_new_tip",
            "提示：新实例创建后，请在设备设置页配置对应的模拟器 serial",
        ))
        tip.setStyleSheet("color: #8a8ea4; font-size: 11px;")
        tip.setWordWrap(True)
        layout.addWidget(tip)

        # 按钮
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self._update_color_highlight()

    def _on_color_selected(self, color: str) -> None:
        self._selected_color = color
        self._update_color_highlight()

    def _update_color_highlight(self) -> None:
        for c, btn in self._color_buttons:
            border = "2px solid #ffffff" if c == self._selected_color else "2px solid transparent"
            btn.setStyleSheet(
                f"background: {c}; border-radius: 12px; border: {border};"
            )

    def _on_accept(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(
                self,
                locale.tr("instance_new_invalid_title", "无效输入"),
                locale.tr("instance_new_empty_name", "请输入实例名称"),
            )
            return
        self.accept()

    def get_values(self) -> tuple:
        """返回 (display_name, color, clone_from)。"""
        return (
            self._name_edit.text().strip(),
            self._selected_color,
            self._clone_combo.currentData(),
        )


class RenameInstanceDialog(QDialog):
    """重命名实例对话框。"""

    def __init__(self, current_name: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(locale.tr("instance_rename_title", "重命名实例"))
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        layout.addWidget(QLabel(locale.tr("instance_rename_new_name", "新名称:")))
        self._name_edit = QLineEdit(current_name)
        layout.addWidget(self._name_edit)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _on_accept(self) -> None:
        if not self._name_edit.text().strip():
            QMessageBox.warning(self, "", locale.tr("instance_rename_empty", "名称不能为空"))
            return
        self.accept()

    def get_name(self) -> str:
        return self._name_edit.text().strip()


class RecolorInstanceDialog(QDialog):
    """修改实例主题色对话框。"""

    def __init__(self, current_color: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(locale.tr("instance_recolor_title", "修改主题色"))
        self._selected_color = current_color

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        layout.addWidget(QLabel(locale.tr("instance_recolor_pick", "选择颜色:")))
        color_row = QHBoxLayout()
        self._color_buttons: list[tuple] = []
        for c in PRESET_COLORS:
            btn = QPushButton()
            btn.setFixedSize(28, 28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"background: {c}; border-radius: 14px; border: 2px solid transparent;"
            )
            btn.clicked.connect(lambda _, color=c: self._on_color_selected(color))
            color_row.addWidget(btn)
            self._color_buttons.append((c, btn))
        color_row.addStretch()
        layout.addLayout(color_row)

        # 自定义颜色按钮
        custom_btn = QPushButton(locale.tr("instance_recolor_custom", "自定义颜色..."))
        custom_btn.clicked.connect(self._on_custom_color)
        layout.addWidget(custom_btn)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self._update_color_highlight()

    def _on_color_selected(self, color: str) -> None:
        self._selected_color = color
        self._update_color_highlight()

    def _on_custom_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._selected_color), self)
        if color.isValid():
            self._selected_color = color.name()
            self._update_color_highlight()

    def _update_color_highlight(self) -> None:
        for c, btn in self._color_buttons:
            border = "2px solid #ffffff" if c == self._selected_color else "2px solid transparent"
            btn.setStyleSheet(
                f"background: {c}; border-radius: 14px; border: {border};"
            )

    def get_color(self) -> str:
        return self._selected_color


class ConfirmDeleteDialog(QDialog):
    """删除实例确认对话框。"""

    def __init__(self, meta: InstanceMeta, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(locale.tr("instance_delete_title", "删除实例"))
        self.setMinimumWidth(400)
        self._confirmed = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        # 警告
        warning = QLabel(
            locale.tr(
                "instance_delete_warning",
                "确定要删除实例 \"{name}\" 吗？\n\n"
                "此操作将删除以下数据，且不可恢复：\n"
                "  • 配置文件（client_config.json）\n"
                "  • 队列状态（maaend_task_state.json）\n"
                "  • 定时任务（scheduled_tasks.json）\n"
                "  • 缓存、日志、脚本录制\n\n"
                "LLM 配置（全局共享）不受影响。"
            ).format(name=meta.display_name)
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #e03131; font-size: 12px;")
        layout.addWidget(warning)

        # 路径显示
        from core.foundation.instance import get_instance_root
        path_label = QLabel(locale.tr(
            "instance_delete_path",
            "数据目录: {path}"
        ).format(path=str(get_instance_root(meta.id))))
        path_label.setStyleSheet("color: #8a8ea4; font-size: 11px;")
        path_label.setWordWrap(True)
        layout.addWidget(path_label)

        # 确认输入
        confirm_label = QLabel(locale.tr(
            "instance_delete_confirm_prompt",
            "请输入实例名称 \"{name}\" 以确认删除:"
        ).format(name=meta.display_name))
        layout.addWidget(confirm_label)
        self._confirm_edit = QLineEdit()
        layout.addWidget(self._confirm_edit)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.button(QDialogButtonBox.StandardButton.Ok).setText(locale.tr("instance_delete_btn", "删除"))
        btn_box.button(QDialogButtonBox.StandardButton.Ok).setStyleSheet("background: #e03131; color: white;")
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _on_accept(self) -> None:
        if self._confirm_edit.text().strip() != self._confirm_edit.text().strip():
            return
        # 验证输入与原始名称匹配（在调用方传入 meta.display_name 校验）
        self._confirmed = True
        self.accept()

    def is_confirmed(self) -> bool:
        return self._confirmed

    def get_confirm_text(self) -> str:
        return self._confirm_edit.text().strip()


__all__ = [
    "ConfirmDeleteDialog",
    "NewInstanceDialog",
    "RecolorInstanceDialog",
    "RenameInstanceDialog",
]
