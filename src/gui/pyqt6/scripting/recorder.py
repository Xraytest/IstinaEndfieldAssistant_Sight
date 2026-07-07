"""Recorder for capturing user interactions on QWidgets."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from PyQt6.QtCore import QObject, QEvent, Qt, QTimer, QPoint
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractScrollArea,
    QScrollBar,
    QAbstractSlider,
    QMenu,
    QDialog,
    QHeaderView,
    QStatusBar,
    QLineEdit,
    QComboBox,
)

from src.gui.pyqt6.scripting.models import Script, ActionRecord

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QMainWindow

logger = logging.getLogger(__name__)

# Widgets to skip entirely during event recording
_SKIPPED_TYPES = (
    QAbstractScrollArea,
    QScrollBar,
    QAbstractSlider,
    QMenu,
    QDialog,
    QHeaderView,
    QStatusBar,
)


class Recorder(QObject):
    """Records user interactions (clicks, text changes) on QWidgets."""

    recording_started = _script = None
    recording_stopped = None

    def __init__(
        self,
        main_window: "QMainWindow",
        save_directory: Optional[Path] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._main_window = main_window
        self._save_directory = save_directory or Path(__file__).resolve().parent.parent.parent.parent / "scripts" / "recorded"
        self._save_directory.mkdir(parents=True, exist_ok=True)
        self._script: Optional[Script] = None
        self._active = False
        self._app_filter_installed = False

        # Debounce timer for text changes (avoid recording every keystroke)
        self._text_timers: dict[str, QTimer] = {}
        self._pending_text: dict[str, str] = {}

    def start(self, name: Optional[str] = None) -> Script:
        """Start a new recording session."""
        if self._active:
            raise RuntimeError("Recording is already in progress")
        self._active = True
        script_name = name or f"script_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self._script = Script(
            name=script_name,
            description="",
            created_at=datetime.now().isoformat(),
        )
        self._install_app_filter()
        logger.info("Recording started: %s", script_name)
        if self.recording_started:
            self.recording_started.emit(script_name)
        return self._script

    def stop(self) -> Optional[Script]:
        """Stop the current recording session and return the script."""
        if not self._active:
            return self._script
        self._active = False
        self._uninstall_app_filter()
        self._text_timers.clear()
        self._pending_text.clear()
        logger.info("Recording stopped: %s", self._script.name if self._script else "N/A")
        if self.recording_stopped:
            self.recording_stopped.emit(self._script.name if self._script else "")
        return self._script

    def save_current_script(self) -> Optional[Path]:
        """Save the current script to disk."""
        if self._script is None:
            return None
        path = self._script.save(self._save_directory)
        logger.info("Script saved to %s", path)
        return path

    def get_current_script(self) -> Optional[Script]:
        """Return the current script."""
        return self._script

    def is_recording(self) -> bool:
        return self._active

    def _install_app_filter(self) -> None:
        """Install the event filter on the QApplication instance to catch all events."""
        app = QApplication.instance()
        if app is not None and not self._app_filter_installed:
            app.installEventFilter(self)
            self._app_filter_installed = True

    def _uninstall_app_filter(self) -> None:
        """Remove the event filter from the QApplication instance."""
        app = QApplication.instance()
        if app is not None and self._app_filter_installed:
            try:
                app.removeEventFilter(self)
            except Exception:
                pass
            self._app_filter_installed = False

    def _should_skip(self, widget: QObject) -> bool:
        """Check if a widget should be skipped during recording."""
        for skipped_type in _SKIPPED_TYPES:
            if isinstance(widget, skipped_type):
                return True
        obj_name = widget.objectName() if hasattr(widget, "objectName") else ""
        if not obj_name and not isinstance(widget, QLineEdit | QComboBox):
            return True
        # Skip internal Qt widgets (usually have no object name)
        if not obj_name:
            return True
        return False

    def _record_click(self, widget: QObject, event: QEvent) -> None:
        """Record a mouse press event."""
        if not isinstance(event, QEvent.Type.MouseButtonPress):
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if not isinstance(widget, QLineEdit | QComboBox):
            # For non-input widgets, record the click
            obj_name = widget.objectName()
            widget_type = type(widget).__name__
            pos = event.position()
            action = ActionRecord(
                widget_type=widget_type,
                object_name=obj_name,
                action_type="click",
                value={"x": pos.x(), "y": pos.y(), "button": int(event.button())},
            )
            self._script.actions.append(action)
            logger.debug("Recorded click on %s (%s) at (%.0f, %.0f)", obj_name, widget_type, pos.x(), pos.y())

    def _record_text_change(self, widget: QObject) -> None:
        """Record a text change with debouncing."""
        obj_name = widget.objectName()
        if not obj_name:
            return
        widget_type = type(widget).__name__
        if isinstance(widget, QLineEdit):
            text = widget.text()
            action_type = "text_changed"
        elif isinstance(widget, QComboBox):
            text = widget.currentText()
            action_type = "combo_changed"
        else:
            return

        # Debounce: cancel previous timer, start new one
        if obj_name not in self._text_timers:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: self._emit_text_action(obj_name, widget_type, action_type, text))
            self._text_timers[obj_name] = timer
        self._pending_text[obj_name] = text
        self._text_timers[obj_name].start(800)

    def _emit_text_action(self, obj_name: str, widget_type: str, action_type: str, text: str) -> None:
        """Actually emit the text change action after debounce."""
        if not self._active:
            return
        # Avoid duplicate consecutive entries
        if self._script and self._script.actions:
            last = self._script.actions[-1]
            if last.action_type == action_type and last.object_name == obj_name and (last.value or {}).get("text") == text:
                return
        action = ActionRecord(
            widget_type=widget_type,
            object_name=obj_name,
            action_type=action_type,
            value={"text": text},
        )
        self._script.actions.append(action)
        logger.debug("Recorded %s on %s: %s", action_type, obj_name, text)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Main event filter installed on QApplication."""
        if not self._active:
            return False

        if self._should_skip(obj):
            return False

        if event.type() == QEvent.Type.MouseButtonPress:
            self._record_click(obj, event)
        elif event.type() == QEvent.Type.FocusOut:
            self._record_text_change(obj)

        return False
