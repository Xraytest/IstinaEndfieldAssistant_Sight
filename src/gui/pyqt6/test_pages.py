"""Test pages - verify all page components can be imported and created"""
import sys

from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget

try:
    from gui.pyqt6.pages import AuthPage, SettingsPage, CloudPage
    from gui.pyqt6.theme import ThemeManager
    print("[OK] All page imports successful")
except ImportError as e:
    print(f"[FAIL] Import failed: {e}")
    sys.exit(1)


def test_pages():
    app = QApplication.instance() or QApplication(sys.argv)
    theme = ThemeManager.get_instance()
    app.setStyleSheet(theme.get_stylesheet())

    window = QMainWindow()
    window.setWindowTitle("IstinaEndfieldAssistant - Page Test")
    window.setGeometry(100, 100, 1200, 800)
    window.setMinimumSize(800, 600)

    central_widget = QWidget()
    window.setCentralWidget(central_widget)
    layout = QVBoxLayout(central_widget)
    layout.setContentsMargins(0, 0, 0, 0)
    tab_widget = QTabWidget()
    layout.addWidget(tab_widget)

    try:
        auth_page = AuthPage()
        tab_widget.addTab(auth_page, "Auth")
        print("[OK] AuthPage created")

        settings_page = SettingsPage()
        tab_widget.addTab(settings_page, "Settings")
        print("[OK] SettingsPage created")

        cloud_page = CloudPage()
        tab_widget.addTab(cloud_page, "Cloud")
        print("[OK] CloudPage created")

    except Exception as e:
        print(f"[FAIL] Page creation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    try:
        auth_page.set_login_status(True, {
            'user_id': 'test_user', 'tier': 'prime', 'login_time': '2026-06-05'
        })
        print("[OK] AuthPage method test successful")

        settings_page.set_config({"inference": {"local": {"enabled": False}}})
        print("[OK] SettingsPage method test successful")

    except Exception as e:
        print(f"[FAIL] Method test failed: {e}")
        import traceback
        traceback.print_exc()

    window.show()
    print("\n=== Test Complete ===")
    print("All pages created and added to tabs")
    sys.exit(app.exec())


if __name__ == '__main__':
    test_pages()