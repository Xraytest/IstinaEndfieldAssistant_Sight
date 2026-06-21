"""PyQt6 message box implementations for Endfield terminal style"""
from PyQt6.QtWidgets import QMessageBox, QWidget
from PyQt6.QtCore import Qt


def _get_parent(parent=None):
    return parent if isinstance(parent, QWidget) else None


def show_info(title: str, message: str, parent=None):
    QMessageBox.information(_get_parent(parent), title, message)


def show_warning(title: str, message: str, parent=None):
    QMessageBox.warning(_get_parent(parent), title, message)


def show_error(title: str, message: str, parent=None):
    QMessageBox.critical(_get_parent(parent), title, message)


def show_success(title: str, message: str, parent=None):
    mb = QMessageBox(_get_parent(parent))
    mb.setIcon(QMessageBox.Icon.Information)
    mb.setWindowTitle(title)
    mb.setText(message)
    mb.setStandardButtons(QMessageBox.StandardButton.Ok)
    mb.setDefaultButton(QMessageBox.StandardButton.Ok)
    mb.exec()


def ask_question(title: str, message: str, parent=None) -> bool:
    reply = QMessageBox.question(
        _get_parent(parent), title, message,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No
    )
    return reply == QMessageBox.StandardButton.Yes


def confirm_action(title: str, message: str, parent=None) -> bool:
    return ask_question(title, message, parent)


def confirm_delete(title: str = "确认删除", message: str = "确定要删除吗？", parent=None) -> bool:
    return ask_question(title, message, parent)


def confirm_exit(title: str = "确认退出", message: str = "确定要退出吗？", parent=None) -> bool:
    return ask_question(title, message, parent)


class MessageBox:
    @staticmethod
    def show_info(title, message, parent=None):
        show_info(title, message, parent)

    @staticmethod
    def show_warning(title, message, parent=None):
        show_warning(title, message, parent)

    @staticmethod
    def show_error(title, message, parent=None):
        show_error(title, message, parent)

    @staticmethod
    def show_success(title, message, parent=None):
        show_success(title, message, parent)

    @staticmethod
    def ask_question(title, message, parent=None) -> bool:
        return ask_question(title, message, parent)


class ProgressDialog:
    def __init__(self, title="Progress", message="Processing...", parent=None):
        self._dialog = QMessageBox(_get_parent(parent))
        self._dialog.setWindowTitle(title)
        self._dialog.setText(message)
        self._dialog.setStandardButtons(QMessageBox.StandardButton.NoButton)

    def set_value(self, value: int):
        self._dialog.setText(f"Processing... {value}%")

    def set_message(self, message: str):
        self._dialog.setText(message)

    def close(self):
        self._dialog.done(0)

    def exec(self):
        self._dialog.exec()