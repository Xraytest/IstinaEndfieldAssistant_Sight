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
    from core.foundation.paths import ensure_src_path
    ensure_src_path(__file__)
    from gui.pyqt6.theme.theme_manager import ThemeManager
    from gui.pyqt6.main_window import MainWindow
    from gui.pyqt6.app_main import (
        PyQt6Application, QtLogHandler, WorkerThread, run_application,
    )
    from gui.pyqt6.pages import AgentPage, AuthPage, SettingsPage
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
    'AgentPage', 'AuthPage', 'SettingsPage',
    'MessageBox', 'ConfirmDialog', 'ProgressDialog',
    'show_info', 'show_warning', 'show_error', 'show_success',
    'ask_question', 'confirm_action', 'confirm_delete', 'confirm_exit',
    'NavigationButton', 'PrimaryButton', 'SecondaryButton',
    'DangerButton', 'CardWidget', 'AgentChatWidget', 'MessageBubble',
]


def create_application(
    agent_executor=None, gui_client=None,
    screen_capture=None, touch_executor=None,
    config=None, inference_manager=None
):
    return PyQt6Application()


def start_gui(
    agent_executor=None, gui_client=None,
    screen_capture=None, touch_executor=None,
    config=None, inference_manager=None
):
    return run_application(
        agent_executor=agent_executor, gui_client=gui_client,
        screen_capture=screen_capture, touch_executor=touch_executor,
        config=config, inference_manager=inference_manager
    )