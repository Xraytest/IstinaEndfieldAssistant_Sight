"""
PyQt6 UI module
"""

try:
    from .theme.theme_manager import ThemeManager
    from .main_window import MainWindow
    from .app_main import (
        PyQt6Application,
        QtLogHandler,
        WorkerThread,
        run_application,
    )
    from .pages import (
        AgentPage,
        AuthPage,
        SettingsPage,
        CloudPage,
    )
    from .dialogs import (
        MessageBox,
        ConfirmDialog,
        ProgressDialog,
        show_info, show_warning, show_error, show_success,
        ask_question, confirm_action, confirm_delete, confirm_exit,
    )
    from .widgets import (
        NavigationButton,
        PrimaryButton,
        SecondaryButton,
        DangerButton,
        CardWidget,
        AgentChatWidget,
        MessageBubble,
    )
except ImportError as e:
    from utils.paths import ensure_src_path
    ensure_src_path(__file__)
    from gui.pyqt6.theme.theme_manager import ThemeManager
    from gui.pyqt6.main_window import MainWindow
    from gui.pyqt6.app_main import (
        PyQt6Application, QtLogHandler, WorkerThread, run_application,
    )
    from gui.pyqt6.pages import AgentPage, AuthPage, SettingsPage, CloudPage
    from gui.pyqt6.dialogs import (
        MessageBox, ConfirmDialog, ProgressDialog,
        show_info, show_warning, show_error, show_success,
        ask_question, confirm_action, confirm_delete, confirm_exit,
    )
    from gui.pyqt6.widgets import (
        NavigationButton, PrimaryButton, SecondaryButton,
        DangerButton, CardWidget, AgentChatWidget, MessageBubble,
    )


__all__ = [
    'ThemeManager', 'MainWindow', 'PyQt6Application',
    'QtLogHandler', 'WorkerThread', 'run_application',
    'AgentPage', 'AuthPage', 'SettingsPage', 'CloudPage',
    'MessageBox', 'ConfirmDialog', 'ProgressDialog',
    'show_info', 'show_warning', 'show_error', 'show_success',
    'ask_question', 'confirm_action', 'confirm_delete', 'confirm_exit',
    'NavigationButton', 'PrimaryButton', 'SecondaryButton',
    'DangerButton', 'CardWidget', 'AgentChatWidget', 'MessageBubble',
]


def create_application(
    auth_manager=None, device_manager=None,
    execution_manager=None, task_queue_manager=None,
    communicator=None, config=None
):
    return PyQt6Application()


def start_gui(
    auth_manager=None, device_manager=None,
    execution_manager=None, task_queue_manager=None,
    communicator=None, config=None
):
    return run_application(
        auth_manager=auth_manager, device_manager=device_manager,
        execution_manager=execution_manager, task_queue_manager=task_queue_manager,
        communicator=communicator, config=config
    )