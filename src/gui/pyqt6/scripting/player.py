"""Player for replaying recorded scripts."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QTimer, QObject, QPoint, pyqtSignal
from PyQt6.QtWidgets import QApplication, QLineEdit, QComboBox
from PyQt6.QtTest import QTest
from PyQt6.QtCore import Qt

from gui.pyqt6.scripting.models import Script, ActionRecord

logger = logging.getLogger(__name__)


class Player(QObject):
    """Replays recorded actions with configurable delays."""

    playback_started = pyqtSignal()
    playback_finished = pyqtSignal()
    playback_stopped = pyqtSignal()

    def __init__(
        self,
        default_delay_ms: int = 500,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._default_delay_ms = default_delay_ms
        self._script: Optional[Script] = None
        self._stopped = False
        self._paused = False
        self._current_index = 0
        self._action_timer: Optional[QTimer] = None

    def load(self, script: Script) -> None:
        """Load a script for playback."""
        self._script = script
        self._current_index = 0
        self._stopped = False
        self._paused = False

    def load_from_file(self, path: Path) -> Script:
        """Load a script from a JSON file."""
        self._script = Script.load(path)
        self._current_index = 0
        self._stopped = False
        self._paused = False
        return self._script

    def play(self, delay_ms: Optional[int] = None) -> None:
        """Start playback."""
        if not self._script or not self._script.actions:
            logger.warning("No script to play")
            return
        self._stopped = False
        self._paused = False
        self._current_index = 0
        delay = delay_ms if delay_ms is not None else self._default_delay_ms
        logger.info("Playback started with delay=%dms", delay)
        if self.playback_started:
            self.playback_started.emit()
        self._schedule_next(delay)

    def pause(self) -> None:
        """Pause playback."""
        self._paused = True
        logger.info("Playback paused at action %d", self._current_index)

    def resume(self) -> None:
        """Resume playback after pause."""
        self._paused = False
        logger.info("Playback resumed at action %d", self._current_index)
        self._schedule_next(self._default_delay_ms)

    def stop(self) -> None:
        """Stop playback immediately."""
        self._stopped = True
        self._paused = False
        if self._action_timer and self._action_timer.isActive():
            self._action_timer.stop()
        logger.info("Playback stopped")
        if self.playback_stopped:
            self.playback_stopped.emit()

    def is_playing(self) -> bool:
        return self._script is not None and not self._stopped and self._current_index < len(self._script.actions)

    def _schedule_next(self, delay_ms: int) -> None:
        """Schedule the next action."""
        if self._stopped:
            self._on_finished()
            return
        if self._paused:
            return
        if self._current_index >= len(self._script.actions):
            self._on_finished()
            return

        action = self._script.actions[self._current_index]
        self._action_timer = QTimer(self)
        self._action_timer.setSingleShot(True)
        self._action_timer.timeout.connect(self._execute_action)
        self._action_timer.start(delay_ms)

    def _execute_action(self) -> None:
        """Execute the current action."""
        if self._stopped or self._paused:
            return
        if not self._script or self._current_index >= len(self._script.actions):
            self._on_finished()
            return

        action = self._script.actions[self._current_index]
        self._current_index += 1

        widget = self._find_widget(action)
        if widget is None:
            logger.warning("Widget not found for action: %s (%s)", action.object_name, action.action_type)
            self._schedule_next(self._default_delay_ms)
            return

        try:
            if action.action_type == "click":
                self._do_click(widget, action)
            elif action.action_type in ("text_changed", "combo_changed"):
                self._do_text(widget, action)
        except Exception as e:
            logger.warning("Failed to execute action %s: %s", action.action_type, e)

        self._schedule_next(self._default_delay_ms)

    def _find_widget(self, action: ActionRecord):
        """Find a widget by object name."""
        app = QApplication.instance()
        if app is None:
            return None
        # Search all top-level widgets recursively
        for widget in app.topLevelWidgets():
            found = widget.findChild(type(None), action.object_name)
            if found is not None:
                return found
        return None

    def _do_click(self, widget, action: ActionRecord) -> None:
        """Synthesize a mouse click."""
        value = action.value or {}
        x = float(value.get("x", 0))
        y = float(value.get("y", 0))
        pos = QPoint(int(x), int(y))
        # Map the position to the widget's local coordinates
        local_pos = widget.mapFromGlobal(widget.mapToGlobal(pos))
        QTest.mouseClick(widget, Qt.MouseButton.LeftButton, pos=local_pos)
        logger.debug("Replayed click on %s at (%.0f, %.0f)", action.object_name, x, y)

    def _do_text(self, widget, action: ActionRecord) -> None:
        """Set text value on a widget."""
        value = action.value or {}
        text = value.get("text", "")
        if isinstance(widget, QLineEdit):
            widget.setText(text)
            widget.editingFinished.emit()
        elif isinstance(widget, QComboBox):
            widget.setCurrentText(text)
        logger.debug("Replayed %s on %s: %s", action.action_type, action.object_name, text)

    def _on_finished(self) -> None:
        """Handle playback completion."""
        self._current_index = 0
        logger.info("Playback finished")
        if self.playback_finished:
            self.playback_finished.emit()
