"""Dialog module stubs"""

from .message_box import (
    MessageBox, ProgressDialog,
    show_info, show_warning, show_error, show_success,
    ask_question, confirm_action, confirm_delete, confirm_exit,
)
from .confirm_dialog import ConfirmDialog
from .local_inference_dialog import LocalInferenceDialog, show_local_inference_dialog

__all__ = [
    'MessageBox', 'ConfirmDialog', 'ProgressDialog',
    'show_info', 'show_warning', 'show_error', 'show_success',
    'ask_question', 'confirm_action', 'confirm_delete', 'confirm_exit',
    'LocalInferenceDialog', 'show_local_inference_dialog',
]