"""
测试页面组件
验证所有页面组件可以正常导入和创建
"""

import sys
import io

# 设置标准输出编码为UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget

# 导入所有页面组件
try:
    from pages import DevicePage, TaskPage, AuthPage, SettingsPage, CloudPage
    from widgets import (
        PrimaryButton, SecondaryButton, DangerButton, CardWidget,
        DevicePreviewWidget, TaskListWidget, DragDropTaskList,
        LogDisplayWidget, SimpleLogDisplay,
        StatusIndicatorWidget, ConnectionStatusIndicator,
    )
    from theme import ThemeManager
    print("[OK] 所有组件导入成功")
except ImportError as e:
    print(f"[FAIL] 导入失败: {e}")
    sys.exit(1)


def test_pages():
    """测试所有页面组件"""
    app = QApplication(sys.argv)
    
    # 应用主题
    theme = ThemeManager.get_instance()
    theme.apply_theme(app)
    
    # 创建主窗口
    window = QMainWindow()
    window.setWindowTitle("IstinaEndfieldAssistant - 页面组件测试")
    window.setGeometry(100, 100, 1200, 800)
    window.setMinimumSize(800, 600)
    
    # 创建中央容器
    central_widget = QWidget()
    window.setCentralWidget(central_widget)
    
    layout = QVBoxLayout(central_widget)
    layout.setContentsMargins(0, 0, 0, 0)
    
    # 创建标签页组件
    tab_widget = QTabWidget()
    layout.addWidget(tab_widget)
    
    # 创建并添加各个页面
    try:
        # 设备管理页面
        device_page = DevicePage()
        tab_widget.addTab(device_page, "设备管理")
        print("[OK] DevicePage 创建成功")
        
        # 任务管理页面
        task_page = TaskPage()
        tab_widget.addTab(task_page, "任务管理")
        print("[OK] TaskPage 创建成功")
        
        # 认证管理页面
        auth_page = AuthPage()
        tab_widget.addTab(auth_page, "账户认证")
        print("[OK] AuthPage 创建成功")
        
        # 设置页面
        settings_page = SettingsPage()
        tab_widget.addTab(settings_page, "设置")
        print("[OK] SettingsPage 创建成功")
        
        # 云服务页面
        cloud_page = CloudPage()
        tab_widget.addTab(cloud_page, "云服务")
        print("[OK] CloudPage 创建成功")
        
    except Exception as e:
        print(f"[FAIL] 页面创建失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # 测试页面方法
    try:
        # 测试DevicePage方法
        device_page.update_device_list([
            {'serial': 'test_device_1', 'model': 'Test Model', 'status': 'device'},
            {'serial': 'test_device_2', 'model': 'Test Model 2', 'status': 'offline'},
        ])
        device_page.set_connected(True, {'serial': 'test_device_1', 'resolution': '1920x1080', 'method': 'android'})
        print("[OK] DevicePage 方法测试成功")
        
        # 测试TaskPage方法
        task_page.add_task('task_1', '测试任务1')
        task_page.add_task('task_2', '测试任务2')
        task_page.update_task_status('task_1', 'running', 50)
        task_page.set_current_task('task_1', '测试任务1')
        print("[OK] TaskPage 方法测试成功")
        
        # 测试AuthPage方法
        auth_page.set_login_status(True, {'user_id': 'test_user', 'tier': 'prime', 'login_time': '2026-04-18'})
        print("[OK] AuthPage 方法测试成功")
        
        # 测试SettingsPage方法
        settings_page.set_current_version('alpha_0.0.1')
        settings_page.set_latest_version('alpha_0.0.2', has_update=True)
        print("[OK] SettingsPage 方法测试成功")
        
        # 测试CloudPage方法
        cloud_page.set_server_status('connected', 'localhost:8080')
        cloud_page.update_user_info({
            'user_id': 'test_user',
            'tier': 'prime',
            'quota_used': 500,
            'quota_daily': 1000,
            'quota_weekly': 6000,
            'quota_monthly': 15000,
            'total_tokens_used': 12345,
            'premium_until': 1735689600,  # 2025-01-01
        })
        print("[OK] CloudPage 方法测试成功")
        
    except Exception as e:
        print(f"[FAIL] 方法测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 显示窗口
    window.show()
    
    print("\n=== 测试完成 ===")
    print("所有页面组件已创建并添加到标签页")
    print("请检查窗口显示是否正常")
    
    sys.exit(app.exec())


if __name__ == '__main__':
    test_pages()