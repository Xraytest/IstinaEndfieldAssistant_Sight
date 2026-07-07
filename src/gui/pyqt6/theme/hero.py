"""Reusable hero header widget for consistent page titles."""

from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout


class HeroHeader(QFrame):
    """统一页面标题区域。

    使用 ``settingsHero`` 作为 objectName，复用 ``theme_manager.py``
    中已定义的 ``QFrame#settingsHero`` QSS 规则。
    """

    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("settingsHero")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setProperty("variant", "hero")
        layout.addWidget(title_label)

        if subtitle:
            summary = QLabel(subtitle)
            summary.setProperty("variant", "secondary")
            layout.addWidget(summary)
