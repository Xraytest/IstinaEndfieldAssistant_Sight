"""Widget settings dialog for configuring individual dashboard widgets."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gui.pyqt6.i18n import get_locale_manager
from gui.pyqt6.theme.widget_styles import CARD_STYLE, INPUT_STYLE

locale = get_locale_manager()


class WidgetSettingsDialog(QDialog):
    """Dialog for configuring a dashboard widget."""

    def __init__(self, widget_id: str, widget_name: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{widget_name} - Settings")
        self.setMinimumWidth(320)
        self._widget_id = widget_id
        self._refresh_interval = 2000
        self._auto_refresh = True
        self._display_mode = "auto"
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # General settings
        general_box = QGroupBox(locale.tr("widget_settings_general", "General"))
        general_box.setStyleSheet(CARD_STYLE)
        form = QFormLayout(general_box)
        form.setSpacing(8)

        self._refresh_spin = QSpinBox()
        self._refresh_spin.setRange(500, 60000)
        self._refresh_spin.setValue(self._refresh_interval)
        self._refresh_spin.setSuffix(" ms")
        self._refresh_spin.setStyleSheet(INPUT_STYLE)
        form.addRow(locale.tr("widget_refresh_interval", "Refresh interval:"), self._refresh_spin)

        self._auto_refresh_check = QCheckBox(locale.tr("widget_auto_refresh", "Auto refresh"))
        self._auto_refresh_check.setChecked(self._auto_refresh)
        form.addRow("", self._auto_refresh_check)

        root.addWidget(general_box)

        # Display settings
        display_box = QGroupBox(locale.tr("widget_settings_display", "Display"))
        display_box.setStyleSheet(CARD_STYLE)
        display_form = QFormLayout(display_box)
        display_form.setSpacing(8)

        self._display_combo = QComboBox()
        self._display_combo.addItems(["Auto", "Compact", "Expanded"])
        self._display_combo.setCurrentText("Auto")
        self._display_combo.setStyleSheet(INPUT_STYLE)
        display_form.addRow(locale.tr("widget_display_mode", "Display mode:"), self._display_combo)

        root.addWidget(display_box)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def settings(self) -> dict:
        return {
            "widget_id": self._widget_id,
            "refresh_interval": self._refresh_spin.value(),
            "auto_refresh": self._auto_refresh_check.isChecked(),
            "display_mode": self._display_combo.currentText().lower(),
        }
