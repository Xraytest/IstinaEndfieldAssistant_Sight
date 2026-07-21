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
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setProperty("variant", "hero")
        layout.addWidget(title_label)

        # Accent divider: a thin rule fading rightward for a polished
        # section-header hierarchy. Decorative only, no behavior change.
        accent = QFrame()
        accent.setFixedHeight(2)
        accent.setMaximumWidth(220)
        accent.setStyleSheet(
            "background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            " stop:0 #19d1ff, stop:0.35 rgba(25, 209, 255, 0.55),"
            " stop:1 rgba(25, 209, 255, 0)); border: none; border-radius: 1px;"
        )
        layout.addWidget(accent)

        if subtitle:
            summary = QLabel(subtitle)
            summary.setProperty("variant", "secondary")
            layout.addWidget(summary)
