"""Scripting page for the PyQt6 GUI."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.pyqt6.i18n import get_locale_manager
from gui.pyqt6.theme.hero import HeroHeader
from gui.pyqt6.theme.icons import get_action_icon
from gui.pyqt6.theme.widget_styles import (
    BTN_ACTIVE,
    BTN_DEFAULT,
    BTN_STOP,
    CARD_STYLE,
    HEADER_STYLE,
    INPUT_STYLE,
    LIST_STYLE,
)

from src.gui.pyqt6.scripting.models import Script, ActionRecord
from src.gui.pyqt6.scripting.player import Player
from src.gui.pyqt6.scripting.recorder import Recorder

locale = get_locale_manager()
logger = logging.getLogger(__name__)

_RECORDINGS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "scripts" / "recorded"


class ScriptingPage(QWidget):
    """Page for recording and playing back UI interaction scripts."""

    def __init__(self, parent: Optional[QWidget] = None, main_window: Optional[QWidget] = None):
        super().__init__(parent)
        self._main_window = main_window
        self._recorder = Recorder(main_window) if main_window else Recorder(None)
        self._player = Player(default_delay_ms=500)
        self._current_script_path: Optional[Path] = None

        self._setup_ui()
        self._refresh_script_list()

        # Connect signals
        self._recorder.recording_started.connect(self._on_recording_started)
        self._recorder.recording_stopped.connect(self._on_recording_stopped)
        self._player.playback_started.connect(self._on_playback_started)
        self._player.playback_finished.connect(self._on_playback_finished)
        self._player.playback_stopped.connect(self._on_playback_stopped)

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)

        # Header
        header = HeroHeader(
            locale.tr("scripting_title", "Script Recorder"),
            locale.tr("scripting_subtitle", "Record and replay UI interactions."),
            self,
        )
        root.addWidget(header)

        # Script list
        list_card = QGroupBox(locale.tr("scripting_scripts", "Available Scripts"))
        list_card.setStyleSheet(CARD_STYLE)
        list_layout = QVBoxLayout(list_card)
        list_layout.setContentsMargins(8, 12, 8, 8)
        list_layout.setSpacing(8)

        self._script_list = QListWidget()
        self._script_list.setStyleSheet(LIST_STYLE)
        self._script_list.setMinimumHeight(200)
        self._script_list.itemDoubleClicked.connect(self._on_script_double_clicked)
        list_layout.addWidget(self._script_list)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._record_btn = QPushButton(locale.tr("scripting_record", "Record"))
        self._record_btn.setStyleSheet(BTN_ACTIVE)
        self._record_btn.setIcon(get_action_icon("录制"))
        self._record_btn.clicked.connect(self._on_record_clicked)
        btn_row.addWidget(self._record_btn)

        self._stop_record_btn = QPushButton(locale.tr("scripting_stop_record", "Stop"))
        self._stop_record_btn.setStyleSheet(BTN_STOP)
        self._stop_record_btn.setEnabled(False)
        self._stop_record_btn.clicked.connect(self._on_stop_record_clicked)
        btn_row.addWidget(self._stop_record_btn)

        self._play_btn = QPushButton(locale.tr("scripting_play", "Play"))
        self._play_btn.setStyleSheet(BTN_DEFAULT)
        self._play_btn.setIcon(get_action_icon("运行"))
        self._play_btn.clicked.connect(self._on_play_clicked)
        btn_row.addWidget(self._play_btn)

        self._delete_btn = QPushButton(locale.tr("scripting_delete", "Delete"))
        self._delete_btn.setStyleSheet(BTN_DEFAULT)
        self._delete_btn.setIcon(get_action_icon("删除"))
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        btn_row.addWidget(self._delete_btn)

        btn_row.addStretch()
        list_layout.addLayout(btn_row)

        root.addWidget(list_card)

        # Status
        self._status_label = QLabel(locale.tr("scripting_status_stopped", "Status: Stopped"))
        self._status_label.setStyleSheet(HEADER_STYLE)
        root.addWidget(self._status_label)

        # Info
        self._info_label = QLabel("")
        self._info_label.setStyleSheet(INPUT_STYLE)
        root.addWidget(self._info_label)

    def _refresh_script_list(self) -> None:
        """Refresh the list of available scripts."""
        self._script_list.clear()
        _RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
        files = sorted(_RECORDINGS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in files:
            try:
                script = Script.load(path)
                item = QListWidgetItem(f"{script.name} ({len(script.actions)} actions)")
                item.setData(Qt.ItemDataRole.UserRole, str(path))
                self._script_list.addItem(item)
            except Exception:
                pass

    def _get_selected_script_path(self) -> Optional[Path]:
        item = self._script_list.currentItem()
        if item is None:
            return None
        path_str = item.data(Qt.ItemDataRole.UserRole)
        if path_str:
            return Path(path_str)
        return None

    def _on_record_clicked(self) -> None:
        """Handle record button click."""
        if self._recorder.is_recording():
            return
        script_name = f"script_{Path(__file__).resolve().name}"  # placeholder, user should rename
        from datetime import datetime
        script_name = f"script_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self._current_script_name = script_name
        self._recorder.start(script_name)
        self._record_btn.setEnabled(False)
        self._stop_record_btn.setEnabled(True)
        self._play_btn.setEnabled(False)
        self._status_label.setText(locale.tr("scripting_status_recording", "Status: Recording..."))
        self._info_label.setText(locale.tr("scripting_record_hint", "Interact with the UI. Click 'Stop' when done."))

    def _on_stop_record_clicked(self) -> None:
        """Handle stop recording button click."""
        script = self._recorder.stop()
        if script:
            path = script.save(_RECORDINGS_DIR)
            self._current_script_path = path
            logger.info("Saved recording to %s", path)
        self._record_btn.setEnabled(True)
        self._stop_record_btn.setEnabled(False)
        self._play_btn.setEnabled(True)
        self._status_label.setText(locale.tr("scripting_status_stopped", "Status: Stopped"))
        actions_count = len(script.actions) if script else 0
        self._info_label.setText(locale.tr("scripting_saved", "Saved {actions} actions to {path}").format(
            actions=actions_count, path=path if script else "N/A"
        ))
        self._refresh_script_list()

    def _on_play_clicked(self) -> None:
        """Handle play button click."""
        if self._player.is_playing():
            return
        script_path = self._get_selected_script_path()
        if not script_path:
            QMessageBox.information(
                self,
                locale.tr("scripting_no_selection", "No Script Selected"),
                locale.tr("scripting_no_selection_msg", "Please select a script to play."),
            )
            return
        try:
            script = self._player.load_from_file(script_path)
            self._current_script_path = script_path
            self._play_btn.setEnabled(False)
            self._record_btn.setEnabled(False)
            self._delete_btn.setEnabled(False)
            self._status_label.setText(locale.tr("scripting_playing", "Status: Playing..."))
            self._info_label.setText(locale.tr("scripting_playing_info", "Playing {actions} actions...").format(
                actions=len(script.actions)
            ))
            self._player.play()
        except Exception as e:
            QMessageBox.critical(
                self,
                locale.tr("scripting_error", "Error"),
                locale.tr("scripting_play_error", "Failed to play script: {error}").format(error=e),
            )
            self._play_btn.setEnabled(True)
            self._record_btn.setEnabled(True)
            self._delete_btn.setEnabled(True)

    def _on_delete_clicked(self) -> None:
        """Handle delete button click."""
        script_path = self._get_selected_script_path()
        if not script_path:
            QMessageBox.information(
                self,
                locale.tr("scripting_no_selection", "No Script Selected"),
                locale.tr("scripting_no_selection_msg", "Please select a script to delete."),
            )
            return
        result = QMessageBox.question(
            self,
            locale.tr("scripting_confirm_delete", "Confirm Delete"),
            locale.tr("scripting_confirm_delete_msg", "Delete script '{name}'?").format(name=script_path.stem),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if result == QMessageBox.StandardButton.Yes:
            try:
                script_path.unlink()
                logger.info("Deleted script: %s", script_path)
                self._refresh_script_list()
                self._info_label.setText("")
            except Exception as e:
                QMessageBox.critical(
                    self,
                    locale.tr("scripting_error", "Error"),
                    locale.tr("scripting_delete_error", "Failed to delete: {error}").format(error=e),
                )

    def _on_script_double_clicked(self, item: QListWidgetItem) -> None:
        """Double-click to play a script."""
        self._on_play_clicked()

    def _on_recording_started(self, name: str) -> None:
        logger.info("Recording started: %s", name)

    def _on_recording_stopped(self, name: str) -> None:
        logger.info("Recording stopped: %s", name)

    def _on_playback_started(self) -> None:
        self._status_label.setText(locale.tr("scripting_playing", "Status: Playing..."))

    def _on_playback_finished(self) -> None:
        self._play_btn.setEnabled(True)
        self._record_btn.setEnabled(True)
        self._delete_btn.setEnabled(True)
        self._status_label.setText(locale.tr("scripting_status_stopped", "Status: Stopped"))
        self._info_label.setText(locale.tr("scripting_finished", "Playback finished."))

    def _on_playback_stopped(self) -> None:
        self._play_btn.setEnabled(True)
        self._record_btn.setEnabled(True)
        self._delete_btn.setEnabled(True)
        self._status_label.setText(locale.tr("scripting_status_stopped", "Status: Stopped"))
        self._info_label.setText(locale.tr("scripting_stopped", "Playback stopped."))
