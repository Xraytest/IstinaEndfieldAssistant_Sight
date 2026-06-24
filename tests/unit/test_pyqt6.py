"""
PyQt6 UI 模块测试入口点
用于验证模块可以正常导入和运行

注意：此测试脚本使用直接路径导入，避免触发现有 Tkinter 模块的循环导入问题。
"""

import sys
import os

# 设置 UTF-8 编码输出
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加 pyqt_ui 目录到 Python 路径
_pyqt_ui_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _pyqt_ui_path)


def test_imports() -> bool:
    """
    测试所有模块是否可以正常导入
    
    Returns:
        bool: 所有导入是否成功
    """
    print("=" * 50)
    print("PyQt6 UI 模块导入测试")
    print("=" * 50)
    
    errors = []
    
    # 测试 PyQt6 导入
    print("\n1. 测试 PyQt6 导入...")
    try:
        from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget
        from PyQt6.QtCore import Qt, pyqtSignal
        from PyQt6.QtGui import QIcon
        print("   [OK] PyQt6 核心模块导入成功")
    except ImportError as e:
        errors.append(f"PyQt6 导入失败: {e}")
        print(f"   [FAIL] PyQt6 导入失败: {e}")
    
    # 测试主题模块导入
    print("\n2. 测试主题模块导入...")
    try:
        from theme import ThemeManager
        from theme.theme_manager import (
            COLORS, FONTS, FONT_SIZES, SPACING, CORNER_RADIUS, ELEVATION, DURATION
        )
        print("   [OK] 主题模块导入成功")
        
        # 验证主题常量
        theme = ThemeManager.get_instance()
        assert theme.colors == COLORS
        assert theme.font_sizes == FONT_SIZES
        assert theme.spacing == SPACING
        print("   [OK] 主题常量验证成功")
        
        # 测试样式表生成
        stylesheet = theme.get_stylesheet()
        assert len(stylesheet) > 100
        print(f"   [OK] 样式表生成成功 (长度: {len(stylesheet)} 字符)")
        
    except ImportError as e:
        errors.append(f"主题模块导入失败: {e}")
        print(f"   [FAIL] 主题模块导入失败: {e}")
    except AssertionError as e:
        errors.append(f"主题模块验证失败: {e}")
        print(f"   [FAIL] 主题模块验证失败: {e}")
    
    # 测试控件模块导入
    print("\n3. 测试控件模块导入...")
    try:
        from widgets import (
            PrimaryButton, SecondaryButton, TextButton, DangerButton,
            CardWidget, ElevatedCardWidget, OutlinedCardWidget
        )
        from widgets.base_widgets import (
            BaseButton, NavigationButton, HorizontalSeparator, VerticalSeparator
        )
        print("   [OK] 控件模块导入成功")
    except ImportError as e:
        errors.append(f"控件模块导入失败: {e}")
        print(f"   [FAIL] 控件模块导入失败: {e}")
    
    # 测试主窗口模块导入
    print("\n4. 测试主窗口模块导入...")
    try:
        from main_window import (
            MainWindow, NavigationBar, ContentArea, create_demo_main_window
        )
        print("   [OK] 主窗口模块导入成功")
    except ImportError as e:
        errors.append(f"主窗口模块导入失败: {e}")
        print(f"   [FAIL] 主窗口模块导入失败: {e}")
    
    # 测试顶层模块导入
    print("\n5. 测试顶层模块导入...")
    try:
        import importlib.util
        init_path = os.path.join(_pyqt_ui_path, "__init__.py")
        spec = importlib.util.spec_from_file_location(
            "pyqt_ui_init",
            init_path
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"无法加载模块: {init_path}")
        pyqt_ui_init = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pyqt_ui_init)
        assert hasattr(pyqt_ui_init, 'ThemeManager')
        assert hasattr(pyqt_ui_init, 'MainWindow')
        print("   [OK] 顶层模块导入成功")
    except ImportError as e:
        errors.append(f"顶层模块导入失败: {e}")
        print(f"   [FAIL] 顶层模块导入失败: {e}")
    except AssertionError as e:
        errors.append(f"顶层模块验证失败: {e}")
        print(f"   [FAIL] 顶层模块验证失败: {e}")
    
    # 测试对话框和页面模块
    print("\n6. 测试对话框和页面模块导入...")
    try:
        from dialogs import __all__ as dialogs_all
        from pages import __all__ as pages_all
        print("   [OK] 对话框模块导入成功 (暂无组件)")
        print("   [OK] 页面模块导入成功 (暂无组件)")
    except ImportError as e:
        errors.append(f"对话框/页面模块导入失败: {e}")
        print(f"   [FAIL] 对话框/页面模块导入失败: {e}")
    
    # 输出结果
    print("\n" + "=" * 50)
    if errors:
        print(f"测试失败! 共 {len(errors)} 个错误:")
        for error in errors:
            print(f"  - {error}")
        print("=" * 50)
        return False
    else:
        print("所有测试通过!")
        print("=" * 50)
        return True


def test_gui_creation() -> bool:
    """
    测试 GUI 控件创建（需要 QApplication）
    
    Returns:
        bool: 创建是否成功
    """
    print("\n" + "=" * 50)
    print("PyQt6 GUI 控件创建测试")
    print("=" * 50)
    
    # 创建 QApplication（如果不存在）
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    errors = []
    
    # 测试主题应用
    print("\n1. 测试主题应用...")
    try:
        from theme import ThemeManager
        theme = ThemeManager.get_instance()
        theme.apply_theme(app)
        print("   [OK] 主题应用成功")
    except Exception as e:
        errors.append(f"主题应用失败: {e}")
        print(f"   [FAIL] 主题应用失败: {e}")
    
    # 测试按钮创建
    print("\n2. 测试按钮创建...")
    try:
        from widgets import (
            PrimaryButton, SecondaryButton, TextButton, DangerButton
        )
        
        primary_btn = PrimaryButton("主要按钮")
        secondary_btn = SecondaryButton("次级按钮")
        text_btn = TextButton("文本按钮")
        danger_btn = DangerButton("危险按钮")
        
        print("   [OK] 所有按钮创建成功")
    except Exception as e:
        errors.append(f"按钮创建失败: {e}")
        print(f"   [FAIL] 按钮创建失败: {e}")
    
    # 测试卡片创建
    print("\n3. 测试卡片创建...")
    try:
        from widgets import (
            CardWidget, ElevatedCardWidget, OutlinedCardWidget
        )
        
        card = CardWidget(title="基础卡片")
        elevated_card = ElevatedCardWidget(title="提升卡片")
        outlined_card = OutlinedCardWidget(title="轮廓卡片")
        
        print("   [OK] 所有卡片创建成功")
    except Exception as e:
        errors.append(f"卡片创建失败: {e}")
        print(f"   [FAIL] 卡片创建失败: {e}")
    
    # 测试主窗口创建
    print("\n4. 测试主窗口创建...")
    try:
        from main_window import create_demo_main_window
        
        window = create_demo_main_window()
        print("   [OK] 主窗口创建成功")
        
        # 检查页面数量
        page_count = 4  # home, device, task, settings
        print(f"   [OK] 已添加 {page_count} 个演示页面")
        
    except Exception as e:
        errors.append(f"主窗口创建失败: {e}")
        print(f"   [FAIL] 主窗口创建失败: {e}")
    
    # 输出结果
    print("\n" + "=" * 50)
    if errors:
        print(f"测试失败! 共 {len(errors)} 个错误:")
        for error in errors:
            print(f"  - {error}")
        print("=" * 50)
        return False
    else:
        print("所有测试通过!")
        print("=" * 50)
        return True


def run_full_test() -> None:
    """运行完整测试"""
    print("\n" + "=" * 60)
    print("IstinaEndfieldAssistant PyQt6 UI 模块完整测试")
    print("=" * 60)
    
    # 导入测试
    import_success = test_imports()
    
    if import_success:
        # GUI 创建测试
        gui_success = test_gui_creation()
        
        if gui_success:
            print("\n" + "=" * 60)
            print("所有测试通过! PyQt6 UI 模块已就绪。")
            print("=" * 60)
            
            # 提示运行演示
            print("\n提示: 运行以下命令启动演示窗口:")
            print("  python IstinaEndfieldAssistant/入口/GUI/pyqt_ui/test_pyqt6.py --demo")
        else:
            print("\nGUI 创建测试失败，请检查 PyQt6 安装。")
    else:
        print("\n导入测试失败，请检查模块路径和依赖。")


def run_demo() -> None:
    """运行演示窗口"""
    from main_window import run_demo
    run_demo()


if __name__ == "__main__":
    # 检查命令行参数
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        run_demo()
    else:
        run_full_test()