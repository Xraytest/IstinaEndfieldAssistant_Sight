"""Dashboard widget market dialog."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.pyqt6.dashboard.widget_registry import get_widget_registry
from gui.pyqt6.i18n import get_locale_manager
from gui.pyqt6.theme.widget_styles import LIST_STYLE

locale = get_locale_manager()


class WidgetMarketDialog(QDialog):
    """Dialog for browsing and adding dashboard widgets."""

    def __init__(self, bridge, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._selected_widget_id: Optional[str] = None
        self.setWindowTitle(locale.tr("widget_market", "Widget Market"))
        self.setMinimumWidth(400)
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel(locale.tr("widget_market", "Widget Market"))
        title.setProperty("variant", "hero")
        root.addWidget(title)

        info = QLabel(locale.tr("widget_market_desc", "Choose widgets to add to your dashboard:"))
        info.setProperty("variant", "secondary")
        root.addWidget(info)

        self._widget_list = QListWidget()
        self._widget_list.setStyleSheet(LIST_STYLE)
        registry = get_widget_registry()
        for widget_id, info in registry.get_available_widgets().items():
            item = QListWidgetItem(f"{info['name']}\n{info['description']}")
            item.setData(1, widget_id)
            self._widget_list.addItem(item)
        self._widget_list.itemSelectionChanged.connect(self._on_selection_changed)
        root.addWidget(self._widget_list)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_add_clicked)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _on_selection_changed(self) -> None:
        items = self._widget_list.selectedItems()
        self._selected_widget_id = items[0].data(1) if items else None

    def _on_add_clicked(self) -> None:
        if self._selected_widget_id:
            self.accept()
        else:
            self.reject()

    def selected_widget_id(self) -> Optional[str]:
        return self._selected_widget_id
