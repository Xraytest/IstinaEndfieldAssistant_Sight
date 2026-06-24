"""
PyQt6 UI module test entry point
Tests module imports and GUI creation
"""
import sys
import os

_pyqt_ui_path = os.path.dirname(os.path.abspath(__file__))
_gui_path = os.path.dirname(_pyqt_ui_path)
_src_path = os.path.dirname(_gui_path)
sys.path.insert(0, _src_path)


def test_imports() -> bool:
    print("=" * 50)
    print("PyQt6 UI Module Import Test")
    print("=" * 50)

    errors = []

    print("\n1. Testing PyQt6 imports...")
    try:
        from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget
        from PyQt6.QtCore import Qt, pyqtSignal
        print("   [OK] PyQt6 core modules imported")
    except ImportError as e:
        errors.append(f"PyQt6 import failed: {e}")
        print(f"   [FAIL] PyQt6 import failed: {e}")

    print("\n2. Testing theme module...")
    try:
        from gui.pyqt6.theme import ThemeManager
        from gui.pyqt6.theme.theme_manager import (
            COLORS, FONTS, FONT_SIZES, SPACING, CORNER_RADIUS, ELEVATION, DURATION
        )
        print("   [OK] Theme module imported")

        theme = ThemeManager.get_instance()
        assert theme.colors == COLORS
        assert theme.font_sizes == FONT_SIZES
        assert theme.spacing == SPACING
        print("   [OK] Theme constants verified")

        stylesheet = theme.get_stylesheet()
        assert len(stylesheet) > 100
        print(f"   [OK] Stylesheet generated ({len(stylesheet)} chars)")

    except ImportError as e:
        errors.append(f"Theme module import failed: {e}")
        print(f"   [FAIL] Theme module import failed: {e}")
    except AssertionError as e:
        errors.append(f"Theme module verification failed: {e}")
        print(f"   [FAIL] Theme module verification failed: {e}")

    print("\n3. Testing widget module...")
    try:
        from gui.pyqt6.widgets import (
            PrimaryButton, SecondaryButton, TextButton, DangerButton,
            CardWidget, ElevatedCardWidget, OutlinedCardWidget
        )
        from gui.pyqt6.widgets.base_widgets import (
            BaseButton, NavigationButton, HorizontalSeparator, VerticalSeparator
        )
        print("   [OK] Widget module imported")
    except ImportError as e:
        errors.append(f"Widget module import failed: {e}")
        print(f"   [FAIL] Widget module import failed: {e}")

    print("\n4. Testing main window module...")
    try:
        from gui.pyqt6.main_window import MainWindow, NavigationBar, ContentArea
        print("   [OK] Main window module imported")
    except ImportError as e:
        errors.append(f"Main window module import failed: {e}")
        print(f"   [FAIL] Main window module import failed: {e}")

    print("\n5. Testing top-level module...")
    try:
        import importlib.util
        init_path = os.path.join(_pyqt_ui_path, "__init__.py")
        spec = importlib.util.spec_from_file_location("pyqt_ui_init", init_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module: {init_path}")
        pyqt_ui_init = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pyqt_ui_init)
        assert hasattr(pyqt_ui_init, 'ThemeManager')
        assert hasattr(pyqt_ui_init, 'MainWindow')
        print("   [OK] Top-level module imported")
    except ImportError as e:
        errors.append(f"Top-level module import failed: {e}")
        print(f"   [FAIL] Top-level module import failed: {e}")
    except AssertionError as e:
        errors.append(f"Top-level module verification failed: {e}")
        print(f"   [FAIL] Top-level module verification failed: {e}")

    print("\n6. Testing dialog and page modules...")
    try:
        from gui.pyqt6.dialogs import __all__ as dialogs_all
        from gui.pyqt6.pages import __all__ as pages_all
        print(f"   [OK] Dialog module imported ({len(dialogs_all)} exports)")
        print(f"   [OK] Page module imported ({len(pages_all)} exports)")
    except ImportError as e:
        errors.append(f"Dialog/page module import failed: {e}")
        print(f"   [FAIL] Dialog/page module import failed: {e}")

    print("\n" + "=" * 50)
    if errors:
        print(f"FAILED! {len(errors)} errors:")
        for error in errors:
            print(f"  - {error}")
        print("=" * 50)
        return False
    else:
        print("All tests passed!")
        print("=" * 50)
        return True


if __name__ == "__main__":
    test_imports()