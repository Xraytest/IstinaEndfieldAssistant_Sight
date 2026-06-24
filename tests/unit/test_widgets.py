"""
PyQt6 核心组件测试脚本
验证阶段2实现的所有组件可正常使用
"""

import sys
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QLabel,
    QFrame,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QColor

# 导入主题管理器
from theme.theme_manager import ThemeManager

# 导入所有组件
from widgets import (
    # 按钮
    PrimaryButton,
    SecondaryButton,
    TextButton,
    DangerButton,
    # 卡片
    CardWidget,
    ElevatedCardWidget,
    OutlinedCardWidget,
    # 设备预览
    DevicePreviewWidget,
    # 任务列表
    TaskListItem,
    DragDropTaskList,
    TaskListWidget,
    # 日志显示
    LogDisplayWidget,
    SimpleLogDisplay,
    # 状态指示器
    StatusIndicatorWidget,
    ConnectionStatusIndicator,
    DualStatusIndicator,
)


class TestMainWindow(QMainWindow):
    """测试主窗口"""
    
    def __init__(self):
        super().__init__()
        
        # 应用主题
        self._theme = ThemeManager.get_instance()
        
        # 设置窗口属性
        self.setWindowTitle("PyQt6 核心组件测试")
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(800, 600)
        
        # 初始化UI
        self._init_ui()
        
        # 应用样式
        self.setStyleSheet(self._theme.get_stylesheet())
    
    def _init_ui(self):
        """初始化UI"""
        # 中央容器
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)
        
        # 标题
        title_label = QLabel("PyQt6 核心组件测试 - 阶段2验证")
        title_label.setProperty("variant", "title")
        title_label.style().unpolish(title_label)
        title_label.style().polish(title_label)
        main_layout.addWidget(title_label)
        
        # 标签页
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget, 1)
        
        # 添加测试页面
        tab_widget.addTab(self._create_buttons_page(), "按钮组件")
        tab_widget.addTab(self._create_cards_page(), "卡片组件")
        tab_widget.addTab(self._create_device_preview_page(), "设备预览")
        tab_widget.addTab(self._create_task_list_page(), "任务列表")
        tab_widget.addTab(self._create_log_display_page(), "日志显示")
        tab_widget.addTab(self._create_status_indicator_page(), "状态指示器")
        
        # 底部状态栏
        status_frame = QFrame()
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(0, 0, 0, 0)
        
        status_indicator = StatusIndicatorWidget()
        status_indicator.set_connected()
        status_layout.addWidget(QLabel("系统状态:"))
        status_layout.addWidget(status_indicator)
        
        status_layout.addStretch()
        
        test_info = QLabel("所有组件已加载成功 [OK]")
        test_info.setProperty("variant", "success")
        test_info.style().unpolish(test_info)
        test_info.style().polish(test_info)
        status_layout.addWidget(test_info)
        
        main_layout.addWidget(status_frame)
    
    def _create_buttons_page(self) -> QWidget:
        """创建按钮测试页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)
        
        # 标题
        layout.addWidget(QLabel("按钮组件测试"))
        
        # 按钮展示
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        btn_layout.addWidget(PrimaryButton("主要按钮"))
        btn_layout.addWidget(SecondaryButton("次级按钮"))
        btn_layout.addWidget(TextButton("文本按钮"))
        btn_layout.addWidget(DangerButton("危险按钮"))
        
        layout.addLayout(btn_layout)
        
        # 卡片容器
        card = CardWidget(title="按钮交互测试")
        card_layout = card.get_content_layout()
        
        # 添加带事件的按钮
        click_count_label = QLabel("点击次数: 0")
        card_layout.addWidget(click_count_label)
        
        click_btn = PrimaryButton("点击我")
        click_count = [0]
        
        def on_click():
            click_count[0] += 1
            click_count_label.setText(f"点击次数: {click_count[0]}")
        
        click_btn.clicked.connect(on_click)
        card_layout.addWidget(click_btn)
        
        layout.addWidget(card)
        layout.addStretch()
        
        return page
    
    def _create_cards_page(self) -> QWidget:
        """创建卡片测试页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)
        
        layout.addWidget(QLabel("卡片组件测试"))
        
        # 不同类型的卡片
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)
        
        # 普通卡片
        card1 = CardWidget(title="普通卡片")
        card1.get_content_layout().addWidget(QLabel("这是一个普通的卡片容器"))
        cards_layout.addWidget(card1)
        
        # 提升卡片
        card2 = ElevatedCardWidget(title="提升卡片")
        card2.get_content_layout().addWidget(QLabel("带有阴影效果的卡片"))
        cards_layout.addWidget(card2)
        
        # 轮廓卡片
        card3 = OutlinedCardWidget(title="轮廓卡片")
        card3.get_content_layout().addWidget(QLabel("带有边框的卡片"))
        cards_layout.addWidget(card3)
        
        layout.addLayout(cards_layout)
        layout.addStretch()
        
        return page
    
    def _create_device_preview_page(self) -> QWidget:
        """创建设备预览测试页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)
        
        layout.addWidget(QLabel("设备预览组件测试"))
        
        # 设备预览组件
        preview = DevicePreviewWidget()
        preview.set_device_status("未连接设备", connected=False)
        layout.addWidget(preview, 1)
        
        # 控制按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        connect_btn = PrimaryButton("模拟连接")
        def on_connect():
            preview.set_device_status("已连接: 模拟设备", connected=True)
            preview.start_auto_refresh()
        connect_btn.clicked.connect(on_connect)
        btn_layout.addWidget(connect_btn)
        
        disconnect_btn = DangerButton("断开连接")
        def on_disconnect():
            preview.stop_auto_refresh()
            preview.set_device_status("未连接", connected=False)
        disconnect_btn.clicked.connect(on_disconnect)
        btn_layout.addWidget(disconnect_btn)
        
        # 模拟图像更新
        update_btn = SecondaryButton("模拟截图")
        def on_update():
            # 创建一个测试图像
            test_image = QImage(400, 300, QImage.Format.Format_RGB32)
            test_image.fill(QColor(67, 97, 238))  # 主色调
            
            # 添加一些文字
            from PyQt6.QtGui import QPainter, QFont
            painter = QPainter(test_image)
            painter.setPen(QColor(255, 255, 255))
            font = QFont()
            font.setPointSize(16)
            painter.setFont(font)
            painter.drawText(test_image.rect(), Qt.AlignmentFlag.AlignCenter, "模拟设备截图")
            painter.end()
            
            preview.update_image_from_qimage(test_image)
        update_btn.clicked.connect(on_update)
        btn_layout.addWidget(update_btn)
        
        layout.addLayout(btn_layout)
        
        return page
    
    def _create_task_list_page(self) -> QWidget:
        """创建任务列表测试页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)
        
        layout.addWidget(QLabel("任务列表组件测试"))
        
        # 任务列表组件
        task_list = TaskListWidget(title="测试任务队列")
        layout.addWidget(task_list, 1)
        
        # 添加一些测试任务
        task_list.add_task("task_1", "任务1 - 数据采集", TaskListItem.STATUS_PENDING)
        task_list.add_task("task_2", "任务2 - 图像处理", TaskListItem.STATUS_RUNNING, progress=45)
        task_list.add_task("task_3", "任务3 - 结果上传", TaskListItem.STATUS_COMPLETED)
        
        # 连接信号
        def on_task_action(task_id, action):
            print(f"任务操作: {task_id} -> {action}")
            if action == "delete":
                task_list.remove_task(task_id)
            elif action == "start":
                task_list.update_task_status(task_id, TaskListItem.STATUS_RUNNING)
            elif action == "stop":
                task_list.update_task_status(task_id, TaskListItem.STATUS_PAUSED)
        
        task_list.task_action_requested.connect(on_task_action)
        
        # 控制按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        add_btn = PrimaryButton("添加任务")
        task_count = [4]
        
        def on_add():
            task_list.add_task(
                f"task_{task_count[0]}",
                f"任务{task_count[0]} - 新任务",
                TaskListItem.STATUS_PENDING
            )
            task_count[0] += 1
        
        add_btn.clicked.connect(on_add)
        btn_layout.addWidget(add_btn)
        
        clear_btn = DangerButton("清除所有")
        clear_btn.clicked.connect(task_list.clear_all_tasks)
        btn_layout.addWidget(clear_btn)
        
        layout.addLayout(btn_layout)
        
        return page
    
    def _create_log_display_page(self) -> QWidget:
        """创建日志显示测试页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)
        
        layout.addWidget(QLabel("日志显示组件测试"))
        
        # 日志显示组件
        log_display = LogDisplayWidget()
        layout.addWidget(log_display, 1)
        
        # 添加一些测试日志
        log_display.append_info("系统启动完成", "SYSTEM")
        log_display.append_debug("加载配置文件", "CONFIG")
        log_display.append_warning("网络连接不稳定", "NETWORK")
        log_display.append_error("设备响应超时", "DEVICE")
        
        # 控制按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        info_btn = PrimaryButton("添加INFO")
        info_btn.clicked.connect(lambda: log_display.append_info("这是一条INFO日志", "TEST"))
        btn_layout.addWidget(info_btn)
        
        warn_btn = SecondaryButton("添加WARNING")
        warn_btn.clicked.connect(lambda: log_display.append_warning("这是一条WARNING日志", "TEST"))
        btn_layout.addWidget(warn_btn)
        
        error_btn = DangerButton("添加ERROR")
        error_btn.clicked.connect(lambda: log_display.append_error("这是一条ERROR日志", "TEST"))
        btn_layout.addWidget(error_btn)
        
        layout.addLayout(btn_layout)
        
        return page
    
    def _create_status_indicator_page(self) -> QWidget:
        """创建状态指示器测试页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)
        
        layout.addWidget(QLabel("状态指示器组件测试"))
        
        # 不同类型的状态指示器
        indicators_layout = QVBoxLayout()
        indicators_layout.setSpacing(16)
        
        # 基本状态指示器
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("基本指示器:"))
        
        indicator1 = StatusIndicatorWidget()
        indicator1.set_connected()
        row1.addWidget(indicator1)
        
        indicator2 = StatusIndicatorWidget()
        indicator2.set_connecting()
        row1.addWidget(indicator2)
        
        indicator3 = StatusIndicatorWidget()
        indicator3.set_disconnected()
        row1.addWidget(indicator3)
        
        indicator4 = StatusIndicatorWidget()
        indicator4.set_error()
        row1.addWidget(indicator4)
        
        row1.addStretch()
        indicators_layout.addLayout(row1)
        
        # 连接状态指示器
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("连接指示器:"))
        
        device_indicator = ConnectionStatusIndicator(connection_type="device")
        device_indicator.set_connected()
        row2.addWidget(device_indicator)
        
        network_indicator = ConnectionStatusIndicator(connection_type="network")
        network_indicator.set_connecting()
        row2.addWidget(network_indicator)
        
        server_indicator = ConnectionStatusIndicator(connection_type="server")
        server_indicator.set_disconnected()
        row2.addWidget(server_indicator)
        
        row2.addStretch()
        indicators_layout.addLayout(row2)
        
        # 双状态指示器
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("双状态指示器:"))
        
        dual_indicator = DualStatusIndicator(labels=("设备", "网络"))
        dual_indicator.set_first_status(StatusIndicatorWidget.STATUS_CONNECTED)
        dual_indicator.set_second_status(StatusIndicatorWidget.STATUS_CONNECTING)
        row3.addWidget(dual_indicator)
        
        row3.addStretch()
        indicators_layout.addLayout(row3)
        
        layout.addLayout(indicators_layout)
        
        # 控制按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        cycle_btn = PrimaryButton("循环状态")
        status_cycle = [
            StatusIndicatorWidget.STATUS_CONNECTED,
            StatusIndicatorWidget.STATUS_CONNECTING,
            StatusIndicatorWidget.STATUS_DISCONNECTED,
            StatusIndicatorWidget.STATUS_ERROR,
        ]
        current_idx = [0]
        
        def on_cycle():
            current_idx[0] = (current_idx[0] + 1) % len(status_cycle)
            indicator1.set_status(status_cycle[current_idx[0]])
        
        cycle_btn.clicked.connect(on_cycle)
        btn_layout.addWidget(cycle_btn)
        
        layout.addLayout(btn_layout)
        layout.addStretch()
        
        return page


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 应用主题
    theme = ThemeManager.get_instance()
    app.setStyleSheet(theme.get_stylesheet())
    
    # 创建并显示主窗口
    window = TestMainWindow()
    window.show()
    
    print("=== PyQt6 核心组件测试 ===")
    print("阶段2验证: 核心组件迁移")
    print("已测试组件:")
    print("  - DevicePreviewWidget: 设备预览")
    print("  - DragDropTaskList/TaskListWidget: 拖拽任务列表")
    print("  - LogDisplayWidget: 日志显示")
    print("  - StatusIndicatorWidget: 状态指示器")
    print("所有组件加载成功!")
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()