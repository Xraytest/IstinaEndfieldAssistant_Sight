"""
PyQt6 应用测试
验证完整应用框架是否可以正常运行
"""

import sys
import os

# 添加当前目录到路径，确保可以导入模块
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)


def test_imports():
    """测试所有模块是否可以正确导入"""
    print("=" * 50)
    print("测试模块导入...")
    print("=" * 50)
    
    errors = []
    
    # 测试主题模块
    try:
        from theme.theme_manager import ThemeManager
        print("[OK] ThemeManager 导入成功")
    except Exception as e:
        errors.append(f"ThemeManager 导入失败: {e}")
        print(f"[FAIL] ThemeManager 导入失败: {e}")
    
    # 测试主窗口模块
    try:
        from main_window import MainWindow, NavigationBar, ContentArea
        print("[OK] MainWindow 导入成功")
    except Exception as e:
        errors.append(f"MainWindow 导入失败: {e}")
        print(f"[FAIL] MainWindow 导入失败: {e}")
    
    # 测试页面模块
    try:
        from pages import DevicePage, TaskPage, AuthPage, SettingsPage, CloudPage
        print("[OK] Pages 导入成功")
    except Exception as e:
        errors.append(f"Pages 导入失败: {e}")
        print(f"[FAIL] Pages 导入失败: {e}")
    
    # 测试对话框模块
    try:
        from dialogs import MessageBox, ConfirmDialog, ProgressDialog
        print("[OK] Dialogs 导入成功")
    except Exception as e:
        errors.append(f"Dialogs 导入失败: {e}")
        print(f"[FAIL] Dialogs 导入失败: {e}")
    
    # 测试控件模块
    try:
        from widgets import (
            NavigationButton, PrimaryButton, SecondaryButton, DangerButton,
            CardWidget, DevicePreviewWidget, TaskListWidget, LogDisplayWidget
        )
        print("[OK] Widgets 导入成功")
    except Exception as e:
        errors.append(f"Widgets 导入失败: {e}")
        print(f"[FAIL] Widgets 导入失败: {e}")
    
    # 测试应用入口模块
    try:
        from app_main import PyQt6Application, QtLogHandler, run_application
        print("[OK] AppMain 导入成功")
    except Exception as e:
        errors.append(f"AppMain 导入失败: {e}")
        print(f"[FAIL] AppMain 导入失败: {e}")
    
    # 注意：pyqt_ui顶层模块导入测试在直接运行此文件时可能失败
    # 因为pyqt_ui包需要从父目录导入。这个测试在包使用时会正常工作。
    
    print()
    if errors:
        print(f"发现 {len(errors)} 个导入错误")
        return False
    else:
        print("所有模块导入成功！")
        return True


def test_theme():
    """测试主题管理器"""
    print("=" * 50)
    print("测试主题管理器...")
    print("=" * 50)
    
    try:
        from theme.theme_manager import ThemeManager
        
        # 获取实例
        theme = ThemeManager.get_instance()
        print("[OK] ThemeManager 实例创建成功")
        
        # 测试颜色获取
        primary_color = theme.get_color('primary')
        print(f"[OK] 主色: {primary_color}")
        
        # 测试间距获取
        padding = theme.get_spacing('padding_md')
        print(f"[OK] 中等间距: {padding}")
        
        # 测试字体获取
        font_size = theme.get_font_size('body_medium')
        print(f"[OK] 正文字号: {font_size}")
        
        print()
        print("主题管理器测试通过！")
        return True
        
    except Exception as e:
        print(f"[FAIL] 主题管理器测试失败: {e}")
        return False


def test_main_window_creation():
    """测试主窗口创建"""
    print("=" * 50)
    print("测试主窗口创建...")
    print("=" * 50)
    
    try:
        from PyQt6.QtWidgets import QApplication
        from main_window import MainWindow
        from theme.theme_manager import ThemeManager
        
        # 创建QApplication（如果不存在）
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 应用主题
        theme = ThemeManager.get_instance()
        theme.apply_theme(app)
        
        # 创建主窗口
        window = MainWindow()
        print("[OK] MainWindow 创建成功")
        
        # 检查窗口属性
        print(f"[OK] 窗口标题: {window.windowTitle()}")
        print(f"[OK] 最小尺寸: {window.minimumWidth()}x{window.minimumHeight()}")
        
        # 检查页面是否已添加
        device_page = window.get_device_page()
        task_page = window.get_task_page()
        auth_page = window.get_auth_page()
        settings_page = window.get_settings_page()
        cloud_page = window.get_cloud_page()
        
        if device_page:
            print("[OK] DevicePage 已添加")
        if task_page:
            print("[OK] TaskPage 已添加")
        if auth_page:
            print("[OK] AuthPage 已添加")
        if settings_page:
            print("[OK] SettingsPage 已添加")
        if cloud_page:
            print("[OK] CloudPage 已添加")
        
        # 测试状态栏
        window.set_status("测试状态")
        print("[OK] 状态栏设置成功")
        
        # 测试版本设置
        window.set_version("v1.0.0-test")
        print("[OK] 版本设置成功")
        
        print()
        print("主窗口创建测试通过！")
        return True
        
    except Exception as e:
        print(f"[FAIL] 主窗口创建测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_pages_creation():
    """测试页面组件创建"""
    print("=" * 50)
    print("测试页面组件创建...")
    print("=" * 50)
    
    try:
        from PyQt6.QtWidgets import QApplication
        from pages import DevicePage, TaskPage, AuthPage, SettingsPage, CloudPage
        from theme.theme_manager import ThemeManager
        
        # 创建QApplication（如果不存在）
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 应用主题
        theme = ThemeManager.get_instance()
        theme.apply_theme(app)
        
        # 创建各页面
        device_page = DevicePage()
        print("[OK] DevicePage 创建成功")
        
        task_page = TaskPage()
        print("[OK] TaskPage 创建成功")
        
        auth_page = AuthPage()
        print("[OK] AuthPage 创建成功")
        
        settings_page = SettingsPage()
        print("[OK] SettingsPage 创建成功")
        
        cloud_page = CloudPage()
        print("[OK] CloudPage 创建成功")
        
        # 测试页面方法
        device_page.set_connected(False)
        print("[OK] DevicePage.set_connected 调用成功")
        
        task_page.update_task_status("test_task", "idle", 0)
        print("[OK] TaskPage.update_task_status 调用成功")
        
        auth_page.set_login_status(False)
        print("[OK] AuthPage.set_login_status 调用成功")
        
        cloud_page.set_server_status("disconnected")
        print("[OK] CloudPage.set_server_status 调用成功")
        
        print()
        print("页面组件创建测试通过！")
        return True
        
    except Exception as e:
        print(f"[FAIL] 页面组件创建测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dialogs():
    """测试对话框组件"""
    print("=" * 50)
    print("测试对话框组件...")
    print("=" * 50)
    
    try:
        from PyQt6.QtWidgets import QApplication
        from dialogs import MessageBox, ConfirmDialog, ProgressDialog
        from theme.theme_manager import ThemeManager
        
        # 创建QApplication（如果不存在）
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 应用主题
        theme = ThemeManager.get_instance()
        theme.apply_theme(app)
        
        # 创建MessageBox（不显示）
        msg_box = MessageBox(message_type=MessageBox.TYPE_INFO)
        msg_box.setWindowTitle("测试")
        msg_box.setText("这是测试消息")
        print("[OK] MessageBox 创建成功")
        
        # 创建ConfirmDialog（不显示）
        confirm_dialog = ConfirmDialog(dialog_type=ConfirmDialog.TYPE_NORMAL)
        confirm_dialog.setWindowTitle("测试确认")
        confirm_dialog.set_message("这是测试确认消息")
        print("[OK] ConfirmDialog 创建成功")
        
        # 创建ProgressDialog（不显示）
        progress_dialog = ProgressDialog(show_cancel=True)
        progress_dialog.setWindowTitle("测试进度")
        progress_dialog.set_message("正在处理...")
        progress_dialog.set_progress(50)
        print("[OK] ProgressDialog 创建成功")
        
        print()
        print("对话框组件测试通过！")
        return True
        
    except Exception as e:
        print(f"[FAIL] 对话框组件测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_app_main():
    """测试应用入口类"""
    print("=" * 50)
    print("测试应用入口类...")
    print("=" * 50)
    
    try:
        from PyQt6.QtWidgets import QApplication
        from app_main import PyQt6Application, QtLogHandler
        from theme.theme_manager import ThemeManager
        
        # 创建QApplication（如果不存在）
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 测试QtLogHandler
        log_handler = QtLogHandler()
        print("[OK] QtLogHandler 创建成功")
        
        # 测试PyQt6Application创建
        pyqt_app = PyQt6Application()
        print("[OK] PyQt6Application 创建成功")
        
        # 测试setup方法
        success = pyqt_app.setup()
        if success:
            print("[OK] PyQt6Application.setup() 成功")
        else:
            print("[FAIL] PyQt6Application.setup() 失败")
            return False
        
        # 获取主窗口
        main_window = pyqt_app.get_main_window()
        if main_window:
            print("[OK] 主窗口获取成功")
        else:
            print("[FAIL] 主窗口获取失败")
            return False
        
        # 测试日志添加
        main_window.append_log("测试日志消息", "INFO")
        print("[OK] 日志添加成功")
        
        # 测试设备状态更新
        main_window.update_device_status("测试状态", False)
        print("[OK] 设备状态更新成功")
        
        # 测试登录状态更新
        main_window.update_login_status(False)
        print("[OK] 登录状态更新成功")
        
        print()
        print("应用入口类测试通过！")
        return True
        
    except Exception as e:
        print(f"[FAIL] 应用入口类测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("PyQt6 应用框架完整测试")
    print("=" * 60 + "\n")
    
    results = []
    
    # 运行各测试
    results.append(("模块导入", test_imports()))
    results.append(("主题管理器", test_theme()))
    results.append(("主窗口创建", test_main_window_creation()))
    results.append(("页面组件", test_pages_creation()))
    results.append(("对话框组件", test_dialogs()))
    results.append(("应用入口类", test_app_main()))
    
    # 输出汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print()
    print(f"总计: {passed} 个通过, {failed} 个失败")
    
    if failed == 0:
        print("\n所有测试通过！PyQt6 应用框架已准备就绪。")
        return True
    else:
        print(f"\n有 {failed} 个测试失败，请检查上述错误信息。")
        return False


def run_demo_window():
    """运行演示窗口"""
    print("\n" + "=" * 60)
    print("启动演示窗口...")
    print("=" * 60 + "\n")
    
    try:
        from PyQt6.QtWidgets import QApplication
        from main_window import MainWindow
        from theme.theme_manager import ThemeManager
        
        # 创建应用
        app = QApplication(sys.argv)
        
        # 应用主题
        theme = ThemeManager.get_instance()
        theme.apply_theme(app)
        
        # 创建主窗口
        window = MainWindow()
        window.show()
        
        print("演示窗口已启动，按 Ctrl+C 或关闭窗口退出。")
        
        # 运行事件循环
        return app.exec()
        
    except Exception as e:
        print(f"启动演示窗口失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="PyQt6 应用测试")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="启动演示窗口而不是运行测试"
    )
    
    args = parser.parse_args()
    
    if args.demo:
        sys.exit(run_demo_window())
    else:
        success = run_all_tests()
        sys.exit(0 if success else 1)