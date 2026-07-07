"""System tray icon support for IstinaEndfieldAssistant Sight.

Provides minimize-to-tray, restore, and context menu actions.
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QObject, QTimer
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
)

from gui.pyqt6.theme.theme_manager import ThemeManager, get_theme


class TrayIcon(QObject):
    """Manages the system tray icon and its interactions."""

    def __init__(self, main_window, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._main_window = main_window
        self._tray: Optional[QSystemTrayIcon] = None
        self._theme_manager: ThemeManager = get_theme()
        self._setup_tray()

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self._tray = QSystemTrayIcon(self._main_window)
        self._tray.setToolTip("Istina Endfield Assistant")

        menu = QMenu()
        show_action = QAction("显示主窗口", self._main_window)
        show_action.triggered.connect(self._show_window)
        menu.addAction(show_action)

        hide_action = QAction("隐藏到托盘", self._main_window)
        hide_action.triggered.connect(self._main_window.hide)
        menu.addAction(hide_action)

        menu.addSeparator()

        quit_action = QAction("退出", self._main_window)
        quit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _show_window(self) -> None:
        self._main_window.show()
        self._main_window.raise_()
        self._main_window.activateWindow()

    def show_message(self, title: str, message: str) -> None:
        if self._tray is None:
            return
        self._tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 3000)

    def is_available(self) -> bool:
        return self._tray is not None and QSystemTrayIcon.isSystemTrayAvailable()
