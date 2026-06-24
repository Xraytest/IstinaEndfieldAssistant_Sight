"""
PyQt6 Core Widget Test
Verifies all widget components can be imported and created
"""
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, QFrame
from PyQt6.QtCore import Qt, QTimer

from theme.theme_manager import ThemeManager

from widgets import (
    PrimaryButton, SecondaryButton, TextButton, DangerButton,
    CardWidget, ElevatedCardWidget, OutlinedCardWidget,
    StatusIndicatorWidget, ConnectionStatusIndicator, DualStatusIndicator,
)


class TestMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._theme = ThemeManager.get_instance()
        self.setWindowTitle("PyQt6 Core Widget Test")
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(800, 600)
        self._init_ui()
        self.setStyleSheet(self._theme.get_stylesheet())

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        title = QLabel("PyQt6 Core Widget Test")
        title.setProperty("variant", "title")
        title.style().unpolish(title)
        title.style().polish(title)
        main_layout.addWidget(title)

        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget, 1)

        tab_widget.addTab(self._create_buttons_page(), "Buttons")
        tab_widget.addTab(self._create_cards_page(), "Cards")
        tab_widget.addTab(self._create_status_indicator_page(), "Status Indicators")

        status_frame = QFrame()
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_indicator = StatusIndicatorWidget()
        status_indicator.set_connected()
        status_layout.addWidget(QLabel("Status:"))
        status_layout.addWidget(status_indicator)
        status_layout.addStretch()
        test_info = QLabel("All widgets loaded [OK]")
        test_info.setProperty("variant", "success")
        test_info.style().unpolish(test_info)
        test_info.style().polish(test_info)
        status_layout.addWidget(test_info)
        main_layout.addWidget(status_frame)

    def _create_buttons_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)
        layout.addWidget(QLabel("Button Component Test"))

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addWidget(PrimaryButton("Primary"))
        btn_layout.addWidget(SecondaryButton("Secondary"))
        btn_layout.addWidget(TextButton("Text"))
        btn_layout.addWidget(DangerButton("Danger"))
        layout.addLayout(btn_layout)

        card = CardWidget(title="Button Interaction Test")
        card_layout = card.get_content_layout()
        click_count_label = QLabel("Click count: 0")
        card_layout.addWidget(click_count_label)
        click_btn = PrimaryButton("Click me")
        click_count = [0]

        def on_click():
            click_count[0] += 1
            click_count_label.setText(f"Click count: {click_count[0]}")

        click_btn.clicked.connect(on_click)
        card_layout.addWidget(click_btn)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _create_cards_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)
        layout.addWidget(QLabel("Card Component Test"))

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)
        card1 = CardWidget(title="Card")
        card1.get_content_layout().addWidget(QLabel("Basic card container"))
        cards_layout.addWidget(card1)
        card2 = ElevatedCardWidget(title="Elevated")
        card2.get_content_layout().addWidget(QLabel("Card with shadow effect"))
        cards_layout.addWidget(card2)
        card3 = OutlinedCardWidget(title="Outlined")
        card3.get_content_layout().addWidget(QLabel("Card with border"))
        cards_layout.addWidget(card3)
        layout.addLayout(cards_layout)
        layout.addStretch()
        return page

    def _create_status_indicator_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)
        layout.addWidget(QLabel("Status Indicator Test"))

        indicators_layout = QVBoxLayout()
        indicators_layout.setSpacing(16)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Basic:"))
        ind1 = StatusIndicatorWidget()
        ind1.set_connected()
        row1.addWidget(ind1)
        ind2 = StatusIndicatorWidget()
        ind2.set_connecting()
        row1.addWidget(ind2)
        ind3 = StatusIndicatorWidget()
        ind3.set_disconnected()
        row1.addWidget(ind3)
        ind4 = StatusIndicatorWidget()
        ind4.set_error()
        row1.addWidget(ind4)
        row1.addStretch()
        indicators_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Connection:"))
        dev_ind = ConnectionStatusIndicator(connection_type="device")
        dev_ind.set_connected()
        row2.addWidget(dev_ind)
        net_ind = ConnectionStatusIndicator(connection_type="network")
        net_ind.set_connecting()
        row2.addWidget(net_ind)
        srv_ind = ConnectionStatusIndicator(connection_type="server")
        srv_ind.set_disconnected()
        row2.addWidget(srv_ind)
        row2.addStretch()
        indicators_layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Dual:"))
        dual = DualStatusIndicator(labels=("Device", "Network"))
        dual.set_first_status(StatusIndicatorWidget.STATUS_CONNECTED)
        dual.set_second_status(StatusIndicatorWidget.STATUS_CONNECTING)
        row3.addWidget(dual)
        row3.addStretch()
        indicators_layout.addLayout(row3)

        layout.addLayout(indicators_layout)

        btn_layout = QHBoxLayout()
        cycle_btn = PrimaryButton("Cycle Status")
        status_cycle = [
            StatusIndicatorWidget.STATUS_CONNECTED,
            StatusIndicatorWidget.STATUS_CONNECTING,
            StatusIndicatorWidget.STATUS_DISCONNECTED,
            StatusIndicatorWidget.STATUS_ERROR,
        ]
        current_idx = [0]

        def on_cycle():
            current_idx[0] = (current_idx[0] + 1) % len(status_cycle)
            ind1.set_status(status_cycle[current_idx[0]])

        cycle_btn.clicked.connect(on_cycle)
        btn_layout.addWidget(cycle_btn)
        layout.addLayout(btn_layout)
        layout.addStretch()
        return page


def main():
    app = QApplication(sys.argv)
    theme = ThemeManager.get_instance()
    app.setStyleSheet(theme.get_stylesheet())
    window = TestMainWindow()
    window.show()
    print("=== PyQt6 Core Widget Test ===")
    print("Tested:")
    print("  - PrimaryButton, SecondaryButton, DangerButton, TextButton")
    print("  - CardWidget, ElevatedCardWidget, OutlinedCardWidget")
    print("  - StatusIndicatorWidget, ConnectionStatusIndicator, DualStatusIndicator")
    print("All widgets loaded successfully!")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()