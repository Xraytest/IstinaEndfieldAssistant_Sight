"""
统一触控管理器 - 管理Android和PC两种触控方式
优先使用Pipeline方式执行任务
"""
import os
import sys
from enum import Enum
from typing import Optional, Tuple, Dict, Any, List
from pathlib import Path
from core.foundation.utils.paths import ensure_src_path

ensure_src_path(__file__)

from core.foundation.logger import get_logger, LogCategory, LogLevel


class TouchDeviceType(Enum):
    """触控设备类型"""
    ANDROID = "android"


class TouchManager:
    """
    统一触控管理器
    
    管理Android和PC两种触控方式，优先使用Pipeline执行任务
    """
    
    def __init__(self):
        self.logger = get_logger()
        self._android_executor = None
        self._device_type: Optional[TouchDeviceType] = None
        self._resolution: Tuple[int, int] = (0, 0)
        self._connected = False
        
        # Pipeline 执行器（优先使用）
        self._tasker = None
        self._resource = None
        self._controller = None
        
    def connect_android(self, 
                        adb_path: str,
                        address: str,
                        screencap_methods: int = 0,
                        input_methods: int = 0,
                        config: Dict = None) -> bool:
        """
        连接Android设备
        
        Args:
            adb_path: ADB可执行文件路径
            address: 设备地址 (如 127.0.0.1:5555)
            screencap_methods: 截图方式
            input_methods: 输入方式
            config: 配置字典
        
        Returns:
            bool: 是否连接成功
        """
        try:
            from .maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig
            
            touch_config = MaaFwTouchConfig(
                adb_path=adb_path,
                address=address,
                screencap_methods=screencap_methods,
                input_methods=input_methods,
                config=config or {}
            )
            
            self._android_executor = MaaFwTouchExecutor(touch_config)
            
            if self._android_executor.connect():
                self._device_type = TouchDeviceType.ANDROID
                self._resolution = self._android_executor.get_resolution()
                self._connected = True
                self._controller = self._android_executor.controller
                self._tasker = self._android_executor.tasker
                self._resource = self._android_executor.resource
                
                self.logger.info(LogCategory.MAIN, "Android设备连接成功",
                                address=address,
                                resolution=f"{self._resolution[0]}x{self._resolution[1]}")
                return True
            else:
                self.logger.exception(LogCategory.MAIN, "Android设备连接失败", address=address)
                return False
                
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "Android设备连接异常", error=str(e))
            return False
    
    def disconnect(self) -> bool:
        """断开连接"""
        try:
            if self._android_executor:
                self._android_executor.disconnect()
            
            self._connected = False
            self._device_type = None
            self._resolution = (0, 0)
            self.logger.info(LogCategory.MAIN, "设备已断开连接")
            return True
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "断开连接异常", error=str(e))
            return False
    
    # ==================== Pipeline优先执行方法 ====================
    
    def run_pipeline_task(self, entry: str, pipeline_override: Dict = None) -> bool:
        """
        执行Pipeline任务（优先推荐）
        
        通过Pipeline JSON定义执行一系列操作，比单次控制更高效
        
        Args:
            entry: 任务入口名称
            pipeline_override: Pipeline覆盖配置
        
        Returns:
            bool: 是否执行成功
        """
        if not self._connected or not self._tasker:
            self.logger.exception(LogCategory.MAIN, "设备未连接，无法执行Pipeline任务")
            return False
        
        try:
            job = self._tasker.post_task(entry, pipeline_override or {})
            job.wait()
            
            if job.succeeded:
                self.logger.debug(LogCategory.MAIN, "Pipeline任务执行成功", entry=entry)
                return True
            else:
                self.logger.exception(LogCategory.MAIN, "Pipeline任务执行失败", entry=entry)
                return False
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "Pipeline任务执行异常", entry=entry, error=str(e))
            return False
    
    def run_pipeline_sequence(self, tasks: List[str]) -> bool:
        """
        执行Pipeline任务序列
        
        Args:
            tasks: 任务入口列表
        
        Returns:
            bool: 是否全部执行成功
        """
        for task in tasks:
            if not self.run_pipeline_task(task):
                return False
        return True
    
    def load_pipeline_resource(self, resource_path: str) -> bool:
        """
        加载Pipeline资源
        
        Args:
            resource_path: 资源路径（包含pipeline JSON和图片）
        
        Returns:
            bool: 是否加载成功
        """
        if not self._resource:
            self.logger.exception(LogCategory.MAIN, "资源未初始化")
            return False
        
        try:
            path = Path(resource_path)
            job = self._resource.post_bundle(path)
            job.wait()
            
            if job.succeeded:
                self.logger.info(LogCategory.MAIN, "Pipeline资源加载成功", path=resource_path)
                return True
            else:
                self.logger.exception(LogCategory.MAIN, "Pipeline资源加载失败", path=resource_path)
                return False
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "Pipeline资源加载异常", error=str(e))
            return False
    
    def override_pipeline(self, pipeline_override: Dict) -> bool:
        """
        动态覆盖Pipeline配置
        
        Args:
            pipeline_override: 覆盖配置字典
        
        Returns:
            bool: 是否覆盖成功
        """
        if not self._resource:
            self.logger.exception(LogCategory.MAIN, "资源未初始化")
            return False
        
        try:
            result = self._resource.override_pipeline(pipeline_override)
            if result:
                self.logger.debug(LogCategory.MAIN, "Pipeline覆盖成功")
            return result
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "Pipeline覆盖异常", error=str(e))
            return False
    
    # ==================== 单次控制方法（备用） ====================

    def safe_press(self, x: int, y: int, duration: int = 50) -> bool:
        """
        安全点击（单次控制，建议优先使用Pipeline）

        Args:
            x: x坐标
            y: y坐标
            duration: 按压时长（毫秒）

        Returns:
            bool: 是否执行成功
        """
        if not self._connected or not self._controller:
            self.logger.exception(LogCategory.MAIN, "设备未连接")
            return False

        try:
            # 坐标直接透传，不做任何缩放

            job = self._controller.post_click(x, y)
            job.wait()

            if job.succeeded:
                self.logger.debug(LogCategory.MAIN, "点击执行成功", x=x, y=y)
                return True
            else:
                self.logger.exception(LogCategory.MAIN, "点击执行失败", x=x, y=y)
                return False
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "点击执行异常", error=str(e))
            return False

    def safe_swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> bool:
        """
        安全滑动（单次控制，建议优先使用Pipeline）

        Args:
            x1: 起点x
            y1: 起点y
            x2: 终点x
            y2: 终点y
            duration: 滑动时长（毫秒）

        Returns:
            bool: 是否执行成功
        """
        if not self._connected or not self._controller:
            self.logger.exception(LogCategory.MAIN, "设备未连接")
            return False

        try:
            # 坐标直接透传，不做任何缩放

            job = self._controller.post_swipe(x1, y1, x2, y2, duration)
            job.wait()

            if job.succeeded:
                self.logger.debug(LogCategory.MAIN, "滑动执行成功",
                                x1=x1, y1=y1, x2=x2, y2=y2, duration=duration)
                return True
            else:
                self.logger.exception(LogCategory.MAIN, "滑动执行失败",
                                x1=x1, y1=y1, x2=x2, y2=y2)
                return False
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "滑动执行异常", error=str(e))
            return False

    def safe_long_press(self, x: int, y: int, duration: int = 1000) -> bool:
        """
        安全长按（单次控制，建议优先使用Pipeline）

        Args:
            x: x坐标
            y: y坐标
            duration: 长按时长（毫秒）

        Returns:
            bool: 是否执行成功
        """
        if not self._connected or not self._controller:
            self.logger.exception(LogCategory.MAIN, "设备未连接")
            return False

        try:
            # 坐标直接透传，不做任何缩放

            # 长按通过touch_down + delay + touch_up实现
            job = self._controller.post_touch_down(x, y)
            job.wait()
            if not job.succeeded:
                return False
            
            # 等待指定时长
            import time
            time.sleep(duration / 1000.0)
            
            job = self._controller.post_touch_up()
            job.wait()
            
            if job.succeeded:
                self.logger.debug(LogCategory.MAIN, "长按执行成功", x=x, y=y, duration=duration)
                return True
            else:
                self.logger.exception(LogCategory.MAIN, "长按执行失败", x=x, y=y)
                return False
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "长按执行异常", error=str(e))
            return False
    
    def screencap(self) -> Optional[Any]:
        """
        截取屏幕
        
        Returns:
            numpy.ndarray: 截图图像（BGR格式）或None
        """
        if not self._connected or not self._controller:
            self.logger.exception(LogCategory.MAIN, "设备未连接")
            return None
        
        try:
            job = self._controller.post_screencap()
            job.wait()
            
            if job.succeeded:
                return self._controller.cached_image
            else:
                self.logger.exception(LogCategory.MAIN, "截图执行失败")
                return None
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "截图执行异常", error=str(e))
            return None
    
    def get_resolution(self) -> Tuple[int, int]:
        """获取设备分辨率"""
        return self._resolution

    def wake_device(self) -> bool:
        """
        设备唤醒 - 发送 KEYCODE_POWER (26)

        Returns:
            bool: 是否执行成功
        """
        if not hasattr(self, '_device_serial') or not self._device_serial:
            self.logger.exception(LogCategory.MAIN, "设备唤醒失败：设备序列号未设置")
            return False

        import subprocess
        from pathlib import Path
        PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
        adb_path = str(PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe")

        self.logger.info(LogCategory.MAIN, "发送设备唤醒指令 (KEYCODE_POWER = 26)")
        cmd = [adb_path, "-s", self._device_serial, "shell", "input", "keyevent", "26"]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            ok = result.returncode == 0
            if ok:
                self.logger.info(LogCategory.MAIN, "设备唤醒成功")
            else:
                self.logger.exception(LogCategory.MAIN, "设备唤醒失败", error=result.stderr.decode('utf-8', errors='replace'))
            return ok
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "设备唤醒异常", error=str(e))
            return False

    @property
    def connected(self) -> bool:
        """是否已连接"""
        return self._connected
    
    @property
    def device_type(self) -> Optional[TouchDeviceType]:
        """设备类型"""
        return self._device_type
    
    # ==================== 工具执行入口 ====================
    
    def execute_tool_call(self, tool_name: str, params: Dict[str, Any]) -> bool:
        """
        统一工具执行入口

        Args:
            tool_name: 工具名称 (click, swipe, long_press, pipeline_task, wake_device)
            params: 参数字典

        Returns:
            bool: 是否执行成功
        """
        if tool_name == "click":
            return self.safe_press(
                params.get("x", 0),
                params.get("y", 0),
                params.get("duration", 50)
            )
        elif tool_name == "swipe":
            return self.safe_swipe(
                params.get("x1", 0),
                params.get("y1", 0),
                params.get("x2", 0),
                params.get("y2", 0),
                params.get("duration", 300)
            )
        elif tool_name == "long_press":
            return self.safe_long_press(
                params.get("x", 0),
                params.get("y", 0),
                params.get("duration", 1000)
            )
        elif tool_name == "pipeline_task":
            return self.run_pipeline_task(
                params.get("entry", ""),
                params.get("pipeline_override", {})
            )
        elif tool_name == "pipeline_sequence":
            return self.run_pipeline_sequence(
                params.get("tasks", [])
            )
        elif tool_name == "open_app":
            # 启动应用程序 - 使用 executor 的封装方法
            app_name = params.get("app_name", "")
            if not app_name:
                self.logger.exception(LogCategory.MAIN, "open_app 缺少 app_name 参数")
                return False

            # 根据设备类型选择对应的 executor
            if self._device_type == TouchDeviceType.ANDROID and self._android_executor:
                return self._android_executor.start_app(app_name)
            else:
                self.logger.exception(LogCategory.MAIN, "控制器未初始化")
                return False
        elif tool_name == "wake_device":
            # 设备唤醒 - 发送 KEYCODE_POWER (26)
            return self.wake_device()
        else:
            self.logger.exception(LogCategory.MAIN, "未知工具名称", tool_name=tool_name)
            return False