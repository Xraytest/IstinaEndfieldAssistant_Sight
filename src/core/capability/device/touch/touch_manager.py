"""
统一触控管理器 - 管理Android和PC两种触控方式
优先使用Pipeline方式执行任务
"""
import os
import sys
from enum import Enum
from typing import Optional, Tuple, Dict, Any, List
from pathlib import Path
from core.foundation.paths import ensure_src_path

ensure_src_path(__file__)

from core.foundation.logger import get_logger, LogCategory, LogLevel

# 延迟导入 ADBDeviceManager 以避免循环依赖
# 在方法内部使用时再导入


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

        # 多种触控方式支持
        self._executors = {
            'MaaTouch': None,
            'minitouch': None,
            'scrcpy': None,
            'nemu_ipc': None,
            'hermit': None,
            'ADB': None  # 始终可用的后备
        }
        self._current_method = None
        self._adb_manager = None
        self._device_serial = None
        
    def connect_android(self,
                        adb_manager: 'ADBDeviceManager',
                        device_serial: str,
                        control_method: str = 'auto',
                        config: Dict = None) -> bool:
        """
        连接Android设备（支持多种触控方式）

        Args:
            adb_manager: ADB设备管理器
            device_serial: 设备序列号
            control_method: 触控方式 ('auto', 'MaaTouch', 'minitouch', 'scrcpy', 'nemu_ipc', 'hermit', 'ADB')
            config: 配置字典

        Returns:
            bool: 是否连接成功
        """
        try:
            self._adb_manager = adb_manager
            self._device_serial = device_serial
            full_config = config or {}

            # 1. 如果 control_method 为 'auto'，查询设备推荐或使用默认顺序
            if control_method == 'auto':
                # 尝试从 ADBDeviceManager 获取设备推荐
                device_info = adb_manager.get_device_info(device_serial)
                if device_info:
                    control_method = device_info.get('recommended_control', 'MaaTouch')
                    self.logger.info(LogCategory.MAIN, "使用设备推荐的触控方式",
                                    device_serial=device_serial,
                                    recommended=control_method,
                                    device_type=device_info.get('type'))
                else:
                    # 默认尝试顺序
                    control_method = 'MaaTouch'
                    self.logger.info(LogCategory.MAIN, "使用默认触控方式", default=control_method)

            # 2. 尝试创建执行器（按优先级）
            method_order = self._determine_method_order(control_method)

            for method in method_order:
                try:
                    executor = self._create_executor_by_method(method, adb_manager, device_serial, full_config)
                    if executor and executor.connect():
                        # 连接成功
                        self._executors[method] = executor
                        self._current_method = method
                        self._resolution = executor.get_resolution()
                        self._connected = True

                        # 设置 Pipeline 执行器（如果支持）
                        if hasattr(executor, 'tasker') and executor.tasker:
                            self._tasker = executor.tasker
                        if hasattr(executor, 'resource') and executor.resource:
                            self._resource = executor.resource
                        if hasattr(executor, 'controller') and executor.controller:
                            self._controller = executor.controller

                        self.logger.info(LogCategory.MAIN, f"触控方式连接成功: {method}",
                                        device_serial=device_serial,
                                        resolution=f"{self._resolution[0]}x{self._resolution[1]}")
                        return True
                    else:
                        if executor:
                            executor.disconnect()
                        self.logger.warning(LogCategory.MAIN, f"触控方式 {method} 连接失败，尝试下一个",
                                           device_serial=device_serial)

                except Exception as e:
                    self.logger.warning(LogCategory.MAIN, f"触控方式 {method} 初始化异常",
                                       device_serial=device_serial, error=str(e))
                    continue

            self.logger.error(LogCategory.MAIN, "所有触控方式均失败", device_serial=device_serial)
            return False

        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "Android设备连接异常", error=str(e))
            return False

    def _determine_method_order(self, preferred_method: str) -> List[str]:
        """
        确定触控方式尝试顺序

        Args:
            preferred_method: 首选方法

        Returns:
            按优先级排序的方法列表
        """
        # 基础降级链
        fallback_map = {
            'MaaTouch': ['MaaTouch', 'minitouch', 'scrcpy', 'ADB'],
            'minitouch': ['minitouch', 'scrcpy', 'ADB'],
            'scrcpy': ['scrcpy', 'MaaTouch', 'ADB'],
            'nemu_ipc': ['nemu_ipc', 'scrcpy', 'MaaTouch', 'ADB'],
            'hermit': ['hermit', 'ADB'],
            'ADB': ['ADB']
        }

        order = fallback_map.get(preferred_method, [preferred_method, 'ADB'])
        # 去重
        seen = set()
        unique_order = []
        for m in order:
            if m not in seen:
                seen.add(m)
                unique_order.append(m)

        return unique_order

    def _create_executor_by_method(self, method: str,
                                   adb_manager: 'ADBDeviceManager',
                                   device_serial: str,
                                   config: Dict) -> Any:
        """
        根据方法名创建执行器

        Args:
            method: 触控方法名
            adb_manager: ADB设备管理器
            device_serial: 设备序列号
            config: 配置字典

        Returns:
            执行器实例或 None
        """
        if method == 'MaaTouch':
            try:
                from .maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig

                maa_config = MaaFwTouchConfig(
                    adb_path=adb_manager.adb_path,
                    address=device_serial,
                    screencap_methods=0,
                    input_methods=3,  # MaaTouch
                    config=config.get('maa_touch', {})
                )
                executor = MaaFwTouchExecutor(maa_config)
                # 保存引用以便后续使用
                self._executors['MaaTouch'] = executor
                return executor
            except ImportError:
                self.logger.warning(LogCategory.MAIN, "MaaFramework 未安装，跳过 MaaTouch")
                return None
            except Exception as e:
                self.logger.warning(LogCategory.MAIN, "MaaTouch 创建失败", error=str(e))
                return None

        elif method == 'minitouch':
            try:
                from .minitouch import MinitouchExecutor
                executor = MinitouchExecutor(
                    adb_manager=adb_manager,
                    device_serial=device_serial,
                    config=config.get('minitouch', {})
                )
                return executor
            except Exception as e:
                self.logger.warning(LogCategory.MAIN, "Minitouch 创建失败", error=str(e))
                return None

        elif method == 'scrcpy':
            # scrcpy 触控需要 ScrcpyCore 的控制 socket
            self.logger.warning(LogCategory.MAIN, "scrcpy 触控尚未实现，回退到 ADB")
            return None

        elif method == 'nemu_ipc':
            self.logger.warning(LogCategory.MAIN, "nemu_ipc 触控尚未实现，回退到 ADB")
            return None

        elif method == 'hermit':
            self.logger.warning(LogCategory.MAIN, "Hermit 触控尚未实现，回退到 ADB")
            return None

        elif method == 'ADB':
            # 创建简单的 ADB 执行器
            return self._create_adb_executor(adb_manager, device_serial)

        else:
            self.logger.error(LogCategory.MAIN, "未知的触控方法", method=method)
            return None

    def _create_adb_executor(self, adb_manager: 'ADBDeviceManager', device_serial: str):
        """创建 ADB 执行器（最简单的回退方案）"""
        class ADBExecutor:
            def __init__(self, adb_manager, serial):
                self.adb_manager = adb_manager
                self.serial = serial
                self.logger = get_logger()
                self.connected = False

            def connect(self) -> bool:
                # ADB 无需特殊连接，只需验证设备可达
                try:
                    adb_manager.get_device_resolution(self.serial)
                    self.connected = True
                    return True
                except Exception:
                    return False

            def disconnect(self) -> bool:
                self.connected = False
                return True

            def get_resolution(self) -> Tuple[int, int]:
                return adb_manager.get_device_resolution(self.serial)

            def click(self, x: int, y: int) -> bool:
                return self._adb_click(x, y)

            def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> bool:
                return self._adb_swipe(x1, y1, x2, y2, duration)

            def long_press(self, x: int, y: int, duration: int = 1000) -> bool:
                return self._adb_swipe(x, y, x, y, duration)

            def _adb_click(self, x: int, y: int) -> bool:
                cmd = f"input tap {x} {y}"
                returncode, _ = adb_manager.shell_command(self.serial, cmd, timeout=5)
                return returncode == 0

            def _adb_swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int) -> bool:
                cmd = f"input swipe {x1} {y1} {x2} {y2} {duration}"
                returncode, _ = adb_manager.shell_command(self.serial, cmd, timeout=5)
                return returncode == 0

        return ADBExecutor(adb_manager, device_serial)
    
    def disconnect(self) -> bool:
        """断开连接"""
        try:
            # 断开所有执行器
            for executor in self._executors.values():
                if executor:
                    try:
                        executor.disconnect()
                    except Exception:
                        pass

            self._connected = False
            self._device_type = None
            self._resolution = (0, 0)
            self._current_method = None
            self._adb_manager = None
            self._device_serial = None
            # 清空执行器引用
            for key in self._executors:
                self._executors[key] = None

            self.logger.info(LogCategory.MAIN, "设备已断开连接")
            return True
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "断开连接异常", error=str(e))
            return False
    
    # ==================== Pipeline优先执行方法 ====================
    

    def _send_keyevent(self, key_code: int) -> bool:
        """
        发送键码事件 - 使用 ADB shell input keyevent

        Args:
            key_code: Android 键码（如 4=返回，3=Home，26=电源）

        Returns:
            bool: 是否执行成功
        """
        if not hasattr(self, '_device_serial') or not self._device_serial:
            self.logger.exception(LogCategory.MAIN, "按键失败：设备序列号未设置")
            return False

        import subprocess
        from pathlib import Path
        PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
        adb_path = str(PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe")

        self.logger.debug(LogCategory.MAIN, f"发送键码：{key_code}")
        cmd = [adb_path, "-s", self._device_serial, "shell", "input", "keyevent", str(key_code)]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            ok = result.returncode == 0
            if ok:
                self.logger.debug(LogCategory.MAIN, f"按键执行成功：{key_code}")
            else:
                self.logger.exception(LogCategory.MAIN, "按键执行失败", error=result.stderr.decode('utf-8', errors='replace'))
            return ok
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "按键执行异常", error=str(e))
            return False


    def run_pipeline_task( entry: str, pipeline_override: Dict = None) -> bool:
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
        安全点击（使用当前触控执行器）

        Args:
            x: x坐标
            y: y坐标
            duration: 按压时长（毫秒），部分执行器可能不支持

        Returns:
            bool: 是否执行成功
        """
        if not self._connected or not self._current_method:
            self.logger.error(LogCategory.MAIN, "设备未连接或未选择触控方式")
            return False

        executor = self._executors.get(self._current_method)
        if not executor:
            self.logger.error(LogCategory.MAIN, "触控执行器未初始化", method=self._current_method)
            return False

        try:
            # 根据执行器类型调用对应方法
            if hasattr(executor, 'safe_press'):
                return executor.safe_press(x, y, duration)
            elif hasattr(executor, 'click'):
                return executor.click(x, y)
            else:
                self.logger.error(LogCategory.MAIN, "执行器不支持点击操作", method=self._current_method)
                return False

        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "点击执行异常", x=x, y=y, error=str(e))
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
        adb_path = str(PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe")

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
        elif tool_name == "press_key":
            # 按键 - 使用 ADB shell input keyevent
            key_code = params.get("key", 4)  # 默认返回键
            return self._send_keyevent(key_code)
        else:
            self.logger.exception(LogCategory.MAIN, "未知工具名称", tool_name=tool_name)
            return False