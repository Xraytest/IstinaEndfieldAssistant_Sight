"""
MaaFramework Android触控适配器
基于MaaFramework的AdbController实现Android设备触控
优先使用Pipeline方式执行任务

注意：MaaFramework通过pip安装（pip install MaaFw），导入名为 maa
"""
import os
import sys
import time
from pathlib import Path
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass

from core.foundation.logger import get_logger, LogCategory, LogLevel

# 尝试导入MaaFramework（pip install MaaFw，导入名 maa）
MAAFW_AVAILABLE = False

try:
    from maa import Library
    from maa.resource import Resource
    from maa.tasker import Tasker
    from maa.controller import AdbController
    from maa.toolkit import Toolkit
    from maa.define import MaaAdbScreencapMethodEnum, MaaAdbInputMethodEnum
    from maa.event_sink import NotificationType
    # 新版本5.10.0在导入maa时已自动初始化Library
    MAAFW_AVAILABLE = True
except ImportError:
    # 定义占位类型
    Tasker = None
    Resource = None
    AdbController = None
    print("警告: MaaFramework库未安装，触控功能将不可用。请使用 pip install MaaFw 安装")


@dataclass
class MaaFwTouchConfig:
    """MaaFramework触控配置"""
    adb_path: str = ""
    address: str = ""
    screencap_methods: int = 0  # MaaAdbScreencapMethodEnum.Default
    input_methods: int = 3  # MaaAdbInputMethodEnum.MaaTouch (默认使用MaaTouch，完全弃用AdbShell)
    config: Dict = None

    # 常用枚举值（供外部直接引用）
    # MaaAdbScreencapMethodEnum: Default=0, AdbShell=1, RawWithGzip=2, RawByNetcat=3, EncodeToFile=4, Minicap=5
    # MaaAdbInputMethodEnum: Default=0, MiniTouch=2, MaaTouch=3 (AdbShell=1 已弃用)
    SCREENCAP_ADB_SHELL: int = 1
    
    # 触控参数
    press_duration_ms: int = 50
    press_jitter_px: int = 2
    swipe_delay_min_ms: int = 100
    swipe_delay_max_ms: int = 300
    use_normalized_coords: bool = True
    
    def __post_init__(self):
        if self.config is None:
            self.config = {}


class MaaFwTouchExecutor:
    """
    MaaFramework触控执行器
    
    基于MaaFramework的AdbController实现，优先使用Pipeline执行任务
    """
    
    def __init__(self, config: MaaFwTouchConfig):
        """
        初始化触控执行器
        
        Args:
            config: MaaFramework触控配置
        """
        self.config = config
        self.logger = get_logger()
        
        # MaaFramework组件
        self._library_loaded = False
        self._resource: Optional[Resource] = None
        self._controller: Optional[AdbController] = None
        self._tasker: Optional[Tasker] = None
        
        # 设备状态
        self._connected = False
        self._resolution: Tuple[int, int] = (0, 0)  # MaaFw 缩放后的分辨率
        self._original_resolution: Tuple[int, int] = (0, 0)  # 设备原始分辨率
        self._uuid = ""
        
    def _load_library(self, lib_path: Optional[str] = None) -> bool:
        """
        加载MaaFramework动态库
        
        注意：MaaFw 5.10.0+ 在导入maa时已自动初始化Library，
        使用包内bin目录的二进制文件。
        此方法主要用于检查库是否可用，以及可选的自定义路径初始化。
        
        Args:
            lib_path: 库路径（可选，新版本通常不需要指定）
        
        Returns:
            bool: 是否加载成功
        """
        if not MAAFW_AVAILABLE:
            self.logger.exception(LogCategory.MAIN, "MaaFramework库未安装")
            return False
        
        if self._library_loaded:
            return True
        
        try:
            # 新版本5.10.0+在导入时已自动初始化Library
            # 如果需要自定义路径，可通过环境变量MAAFW_BINARY_PATH设置
            # 这里我们直接标记为已加载，因为导入时已完成初始化
            self._library_loaded = True
            self.logger.info(LogCategory.MAIN, "MaaFramework库已自动初始化（pip安装版本）")
            return True
            
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "MaaFramework库加载失败", error=str(e))
            return False
    
    def connect(self) -> bool:
        """
        连接Android设备
        
        修复：处理emulator-5562等模拟器设备名到IP:PORT的转换
        
        Returns:
            bool: 是否连接成功
        """
        if not self._load_library():
            return False
        
        try:
            # 初始化Toolkit配置（可选）
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            config_dir = os.path.join(project_root, "config")
            maa_option_path = os.path.join(config_dir, "maa_option.json")
            
            if os.path.exists(maa_option_path):
                Toolkit.init_option(Path(config_dir))
                self.logger.debug(LogCategory.MAIN, "MaaToolkit配置初始化完成")
            
            # 创建资源
            self._resource = Resource()
            self.logger.debug(LogCategory.MAIN, "Resource创建完成")
            
            # 使用Toolkit自动发现设备信息（解决MuMu等模拟器需要专用配置的问题）
            adb_path = self.config.adb_path
            address = self.config.address
            screencap_methods = self.config.screencap_methods
            input_methods = self.config.input_methods
            device_config = self.config.config
            
            # 解析模拟器设备名：emulator-5562 → 127.0.0.1:5562
            if address and address.startswith("emulator-"):
                port_part = address.replace("emulator-", "")
                if port_part.isdigit():
                    resolved_address = f"127.0.0.1:{port_part}"
                    self.logger.info(LogCategory.MAIN, "解析模拟器地址",
                                    original=address,
                                    resolved=resolved_address)
                    address = resolved_address
            
            # 尝试使用Toolkit.find_adb_devices()查找目标设备
            try:
                discovered_devices = Toolkit.find_adb_devices()
                self.logger.debug(LogCategory.MAIN, f"Toolkit发现{len(discovered_devices)}个ADB设备")
                
                # 查找匹配目标地址的设备
                for dev in discovered_devices:
                    if dev.address == address:
                        self.logger.info(LogCategory.MAIN, "使用Toolkit发现的设备信息",
                                        name=dev.name,
                                        adb_path=dev.adb_path,
                                        address=dev.address,
                                        screencap_methods=dev.screencap_methods,
                                        config=str(dev.config))
                        adb_path = dev.adb_path
                        screencap_methods = dev.screencap_methods
                        input_methods = dev.input_methods
                        device_config = dev.config
                        break
                        
            except Exception as e:
                self.logger.warning(LogCategory.MAIN, "Toolkit.find_adb_devices失败，使用默认配置",
                                   error=str(e))
            
            # 创建ADB控制器（使用发现或默认的设备信息）
            self._controller = AdbController(
                adb_path=Path(adb_path),
                address=address,
                screencap_methods=screencap_methods,
                input_methods=input_methods,
                config=device_config
            )
            self.logger.debug(LogCategory.MAIN, "AdbController创建完成",
                             adb_path=adb_path,
                             address=address,
                             screencap_methods=screencap_methods)
            
            # 连接设备
            job = self._controller.post_connection()
            job.wait()
            
            if not job.succeeded:
                self.logger.exception(LogCategory.MAIN, "ADB控制器连接失败")
                return False
            
            # 获取设备信息
            self._uuid = self._controller.uuid

            # 查询设备原始分辨率（通过ADB获取，不受MaaFw缩放影响）
            try:
                import subprocess
                result = subprocess.run(
                    [adb_path, "-s", address, "shell", "wm", "size"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    # 输出格式: "Physical size: 1080x1920"
                    import re
                    match = re.search(r"(\d+)x(\d+)", result.stdout)
                    if match:
                        w, h = int(match.group(1)), int(match.group(2))
                        # wm size 返回竖屏分辨率（如1080x1920），
                        # 但调用方使用横屏坐标空间（1920x1080），需要交换
                        if h > w:
                            # 竖屏 → 横屏：交换宽高
                            self._original_resolution = (h, w)
                            self.logger.debug(LogCategory.MAIN, "原始分辨率查询成功（已转为横屏）",
                                             original=f"{h}x{w}")
                        else:
                            self._original_resolution = (w, h)
                            self.logger.debug(LogCategory.MAIN, "原始分辨率查询成功",
                                             original=f"{w}x{h}")
            except Exception as e:
                self.logger.warning(LogCategory.MAIN, "原始分辨率查询失败", error=str(e))

            # 连接成功后需要先截图才能获取cached_image
            screencap_job = self._controller.post_screencap()
            screencap_job.wait()
            
            if screencap_job.succeeded:
                cached_image = self._controller.cached_image
                if cached_image is not None:
                    self._resolution = (cached_image.shape[1], cached_image.shape[0])
                    self.logger.debug(LogCategory.MAIN, "初始截图成功",
                                     resolution=f"{self._resolution[0]}x{self._resolution[1]}")
                else:
                    self.logger.warning(LogCategory.MAIN, "初始截图返回空图像")
            else:
                self.logger.warning(LogCategory.MAIN, "初始截图失败，将使用默认分辨率")
            
            # 创建Tasker并绑定
            self._tasker = Tasker()
            if not self._tasker.bind(self._resource, self._controller):
                self.logger.exception(LogCategory.MAIN, "Tasker绑定失败")
                return False
            
            self._connected = True
            self.logger.info(LogCategory.MAIN, "Android设备连接成功",
                            uuid=self._uuid,
                            resolution=f"{self._resolution[0]}x{self._resolution[1]}")
            return True
            
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "Android设备连接异常", error=str(e))
            return False
    
    def disconnect(self) -> bool:
        """
        断开设备连接
        
        Returns:
            bool: 是否断开成功
        """
        try:
            self._connected = False
            self._tasker = None
            self._controller = None
            self._resource = None
            self.logger.info(LogCategory.MAIN, "Android设备已断开")
            return True
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "断开连接异常", error=str(e))
            return False
    
    # ==================== Pipeline优先方法 ====================
    
    def load_pipeline(self, pipeline_path: str) -> bool:
        """
        加载Pipeline资源
        
        Args:
            pipeline_path: Pipeline JSON文件路径或资源目录
        
        Returns:
            bool: 是否加载成功
        """
        if not self._connected or not self._resource:
            self.logger.exception(LogCategory.MAIN, "设备未连接，无法加载Pipeline")
            return False
        
        try:
            path = Path(pipeline_path)
            job = self._resource.post_bundle(path)
            job.wait()
            
            if job.succeeded:
                self.logger.info(LogCategory.MAIN, "Pipeline资源加载成功", path=pipeline_path)
                return True
            else:
                self.logger.exception(LogCategory.MAIN, "Pipeline资源加载失败", path=pipeline_path)
                return False
                
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "Pipeline加载异常", error=str(e))
            return False
    
    def run_pipeline_task(self, entry: str, pipeline_override: Dict = None) -> bool:
        """
        执行Pipeline任务（推荐方式）
        
        通过Pipeline JSON定义执行复杂任务，比单次控制更高效
        
        Args:
            entry: 任务入口名称
            pipeline_override: 动态覆盖配置
        
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
                self.logger.warning(LogCategory.MAIN, "Pipeline任务执行失败", entry=entry)
                return False
                
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "Pipeline任务执行异常", entry=entry, error=str(e))
            return False
    
    def run_pipeline_sequence(self, tasks: list) -> bool:
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
    
    def override_pipeline(self, pipeline_override: Dict) -> bool:
        """
        动态覆盖Pipeline配置
        
        Args:
            pipeline_override: 覆盖配置字典
        
        Returns:
            bool: 是否覆盖成功
        """
        if not self._connected or not self._resource:
            self.logger.exception(LogCategory.MAIN, "设备未连接")
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


    def _convert_to_maa_coords(self, x: int, y: int) -> tuple:
        """
        将原始分辨率坐标转换为 MaaFw 坐标空间（修复 3.5）
        
        Args:
            x: 原始分辨率 x 坐标
            y: 原始分辨率 y 坐标
            
        Returns:
            tuple: (maa_x, maa_y) MaaFw 坐标
        """
        if self._original_resolution[0] == 0 or self._original_resolution[1] == 0:
            # 未获取到原始分辨率，直接使用输入坐标
            return x, y
        
        if self._resolution[0] == 0 or self._resolution[1] == 0:
            # 未获取到 MaaFw 分辨率，直接使用输入坐标
            return x, y
        
        # 计算缩放比例
        scale_x = self._resolution[0] / self._original_resolution[0]
        scale_y = self._resolution[1] / self._original_resolution[1]
        
        maa_x = int(x * scale_x)
        maa_y = int(y * scale_y)
        
        return maa_x, maa_y

    def post_click(self, x: int, y: int):
        """点击（返回 Job 对象）"""
        if not self._connected or not self._controller:
            return None
        try:
            if self.config.press_jitter_px > 0:
                import random
                x += random.randint(-self.config.press_jitter_px, self.config.press_jitter_px)
                y += random.randint(-self.config.press_jitter_px, self.config.press_jitter_px)
            return self._controller.post_click(x, y)
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "点击执行异常", error=str(e))
            return None

    def post_keyevent(self, key_code: int):
        """按键事件（返回 Job 对象）
        
        注意：使用 post_press_key 替代 post_keyevent（MaaFw 5.10.0+）
        """
        if not self._connected or not self._controller:
            return None
        try:
            # MaaFw 5.10.0+ 使用 post_press_key 替代 post_keyevent
            return self._controller.post_press_key(key_code)
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "按键执行异常", error=str(e))
            return None

    def post_swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300):
        """滑动（返回 Job 对象）"""
        if not self._connected or not self._controller:
            return None
        try:
            if self.config.swipe_delay_min_ms > 0 and self.config.swipe_delay_max_ms > 0:
                import random
                actual_duration = random.randint(
                    max(duration, self.config.swipe_delay_min_ms),
                    duration + self.config.swipe_delay_max_ms
                )
            else:
                actual_duration = duration
            return self._controller.post_swipe(x1, y1, x2, y2, actual_duration)
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "滑动执行异常", error=str(e))
            return None

    def safe_press(self, x: int, y: int, duration: int = 0) -> bool:
        """安全点击（带等待和结果检查）

        Args:
            x: X 坐标
            y: Y 坐标
            duration: 按下持续时间（毫秒），0 表示使用配置默认值
        """
        job = self.post_click(x, y)
        if job is None:
            return False
        job.wait()
        actual_duration = duration if duration > 0 else self.config.press_duration_ms
        if actual_duration > 0:
            time.sleep(actual_duration / 1000.0)
        return job.succeeded

    def safe_swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> bool:
        """安全滑动（带等待和结果检查）"""
        job = self.post_swipe(x1, y1, x2, y2, duration)
        if job is None:
            return False
        job.wait()
        return job.succeeded

    def click(self, x: int, y: int) -> bool:
        """
        点击（单次控制，建议优先使用Pipeline）

        Args:
            x: x坐标（MaaFw截图空间 1280x720）
            y: y坐标

        Returns:
            bool: 是否执行成功
        """
        if not self._connected or not self._controller:
            self.logger.exception(LogCategory.MAIN, "设备未连接")
            return False

        try:
            # 修复 3.5：坐标转换（原始分辨率 → MaaFw 空间）
            if self.config.use_normalized_coords:
                # 调用方传入原始分辨率坐标，需要转换
                x, y = self._convert_to_maa_coords(x, y)
                self.logger.debug(LogCategory.MAIN, "坐标转换",
                                original=f"{x}/{y}", maa=f"{x}/{y}",
                                scale=f"{self._resolution[0]}/{self._original_resolution[0]}")

            # 应用抖动（如果配置启用）
            if self.config.press_jitter_px > 0:
                import random
                x += random.randint(-self.config.press_jitter_px, self.config.press_jitter_px)
                y += random.randint(-self.config.press_jitter_px, self.config.press_jitter_px)

            job = self._controller.post_click(x, y)
            job.wait()

            # 添加按压延时
            if self.config.press_duration_ms > 0:
                time.sleep(self.config.press_duration_ms / 1000.0)

            if job.succeeded:
                self.logger.debug(LogCategory.MAIN, "点击执行成功", x=x, y=y)
                return True
            else:
                self.logger.exception(LogCategory.MAIN, "点击执行失败", x=x, y=y)
                return False

        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "点击执行异常", error=str(e))
            return False
    
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> bool:
        """
        滑动（单次控制，建议优先使用Pipeline）
        
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
            # 修复 3.5：坐标转换（原始分辨率 → MaaFw 空间）
            if self.config.use_normalized_coords:
                x1, y1 = self._convert_to_maa_coords(x1, y1)
                x2, y2 = self._convert_to_maa_coords(x2, y2)
                self.logger.debug(LogCategory.MAIN, "滑动坐标转换",
                                original=f"({x1},{y1})→({x2},{y2})",
                                scale=f"{self._resolution[0]}/{self._original_resolution[0]}")

            # 应用滑动延时随机化
            if self.config.swipe_delay_min_ms > 0 and self.config.swipe_delay_max_ms > 0:
                import random
                actual_duration = random.randint(
                    max(duration, self.config.swipe_delay_min_ms),
                    duration + self.config.swipe_delay_max_ms
                )
            else:
                actual_duration = duration
            
            job = self._controller.post_swipe(x1, y1, x2, y2, actual_duration)
            job.wait()
            
            if job.succeeded:
                self.logger.debug(LogCategory.MAIN, "滑动执行成功",
                                x1=x1, y1=y1, x2=x2, y2=y2, duration=actual_duration)
                return True
            else:
                self.logger.exception(LogCategory.MAIN, "滑动执行失败",
                                x1=x1, y1=y1, x2=x2, y2=y2)
                return False
                
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "滑动执行异常", error=str(e))
            return False
    
    def long_press(self, x: int, y: int, duration: int = 1000) -> bool:
        """
        长按（单次控制，建议优先使用Pipeline）
        
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
            # 坐标转换（原始分辨率 → MaaFw 空间），与 click()/swipe() 保持一致
            if self.config.use_normalized_coords:
                x, y = self._convert_to_maa_coords(x, y)
                self.logger.debug(LogCategory.MAIN, "长按坐标转换",
                                original=f"{x}/{y}", maa=f"{x}/{y}",
                                scale=f"{self._resolution[0]}/{self._original_resolution[0]}")

            # 应用抖动
            if self.config.press_jitter_px > 0:
                import random
                x += random.randint(-self.config.press_jitter_px, self.config.press_jitter_px)
                y += random.randint(-self.config.press_jitter_px, self.config.press_jitter_px)

            # 使用touch_down + touch_up实现长按
            job = self._controller.post_touch_down(x, y)
            job.wait()
            
            if not job.succeeded:
                return False
            
            # 等待
            time.sleep(duration / 1000.0)
            
            # 抬起
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
    
    def screencap(self) -> Optional[any]:
        """
        截图
        
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
                self.logger.warning(LogCategory.MAIN, "截图失败")
                return None
                
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "截图异常", error=str(e))
            return None
    
    def get_resolution(self) -> Tuple[int, int]:
        """
        获取设备分辨率
        
        Returns:
            Tuple[int, int]: (width, height)
        """
        if self._resolution == (0, 0) and self._controller:
            try:
                image = self.screencap()
                if image is not None:
                    self._resolution = (image.shape[1], image.shape[0])
            except Exception as e:
                self.logger.debug(LogCategory.MAIN, f"通过截图获取分辨率失败：{e}")
                pass
        return self._resolution
    
    def post_ocr_model(self, model_path: str) -> bool:
        """
        加载 OCR 模型（MaaFw 5.11.1+）
        
        Args:
            model_path: OCR 模型目录路径
            
        Returns:
            bool: 是否加载成功
        """
        if not self._connected or not self._resource:
            self.logger.exception(LogCategory.MAIN, "设备未连接，无法加载 OCR 模型")
            return False
        
        try:
            job = self._resource.post_ocr_model(Path(model_path))
            job.wait()
            
            if job.succeeded:
                self.logger.info(LogCategory.MAIN, "OCR 模型加载成功", path=model_path)
                return True
            else:
                self.logger.warning(LogCategory.MAIN, "OCR 模型加载失败", path=model_path)
                return False
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "OCR 模型加载异常", error=str(e))
            return False
    
    def ocr(self, roi: tuple = None, expected: list = None, threshold: float = 0.3,
            only_rec: bool = True, model: str = '') -> list:
        """
        OCR 识别（通过 MaaFw Tasker.post_recognition + JOCR）
        
        MaaFw 5.11.1+ 使用 post_recognition 执行 OCR 识别
        
        Args:
            roi: 识别区域 (x, y, w, h)，None 表示全屏
            expected: 期望匹配的文本列表
            threshold: 识别阈值（默认 0.3）
            only_rec: 仅识别不匹配（默认 True，返回所有识别结果）
            model: OCR 模型名称（可选）
            
        Returns:
            OCR 结果列表：[{\"text\": str, \"box\": [x,y,w,h], \"score\": float}, ...]
        """
        if not self._connected or not self._tasker or not self._controller:
            self.logger.exception(LogCategory.MAIN, "设备未连接，无法执行 OCR")
            return []
        
        try:
            # 获取截图
            image = self.screencap()
            if image is None:
                self.logger.warning(LogCategory.MAIN, "截图失败，无法执行 OCR")
                return []
            
            # 导入 JOCR（延迟导入，避免循环依赖）
            from maa.pipeline import JOCR
            
            # 构建 ROI 参数
            if roi is None:
                # 使用控制器缓存图像的完整尺寸
                cached_image = self._controller.cached_image
                if cached_image is not None:
                    h, w = cached_image.shape[:2]
                    roi_tuple = (0, 0, w, h)
                else:
                    roi_tuple = (0, 0, 0, 0)
            else:
                roi_tuple = tuple(roi) if len(roi) == 4 else (0, 0, 0, 0)
            
            # 构建 JOCR 参数
            jocr_param = JOCR(
                expected=expected or [],
                roi=roi_tuple,
                threshold=threshold,
                only_rec=only_rec,
                model=model
            )
            
            # 执行识别
            from maa.pipeline import JRecognitionType
            job = self._tasker.post_recognition(JRecognitionType.OCR, jocr_param, image)
            job.wait()
            
            if job.succeeded:
                results = job.get()
                # 解析结果
                return self._parse_ocr_results(results)
            else:
                self.logger.warning(LogCategory.MAIN, "OCR 识别任务失败")
                return []
                
        except ImportError as e:
            self.logger.exception(LogCategory.MAIN, "JOCR 导入失败", error=str(e))
            return []
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "OCR 执行异常", error=str(e))
            return []
    
    def _parse_ocr_results(self, results: Any) -> list:
        """
        解析 OCR 识别结果
        
        Args:
            results: post_recognition 返回的结果
            
        Returns:
            标准化 OCR 结果列表
        """
        if not results:
            return []
        
        normalized = []
        
        # 结果可能是单个识别结果或列表
        if not isinstance(results, list):
            results = [results]
        
        for item in results:
            try:
                # MaaFw 识别结果格式：
                # - matched: bool - 是否匹配到 expected
                # - text: str - 识别到的文本
                # - box: tuple - [x, y, w, h]
                # - score: float - 置信度（可能没有）
                
                text = getattr(item, 'text', '') or ''
                if not text.strip():
                    continue
                
                box_attr = getattr(item, 'box', None)
                if box_attr:
                    if isinstance(box_attr, (tuple, list)) and len(box_attr) >= 4:
                        box = [int(box_attr[0]), int(box_attr[1]), 
                               int(box_attr[2]), int(box_attr[3])]
                    else:
                        box = [0, 0, 0, 0]
                else:
                    box = [0, 0, 0, 0]
                
                score = getattr(item, 'score', 1.0)
                if score is None:
                    score = 1.0
                
                # 过滤低置信度结果
                if score < 0.3:
                    continue
                
                x, y, w, h = box
                cx = x + w // 2
                cy = y + h // 2
                
                normalized.append({
                    "text": text.strip(),
                    "box": box,
                    "cx": cx,
                    "cy": cy,
                    "score": float(score),
                    "matched": getattr(item, 'matched', False)
                })
                
            except Exception as e:
                self.logger.debug(LogCategory.MAIN, f"解析单个 OCR 结果失败：{e}")
                continue
        
        return normalized
    
    def start_app(self, package_name: str) -> bool:
        """
        启动应用
        
        Args:
            package_name: 应用包名
        
        Returns:
            bool: 是否启动成功
        """
        if not self._connected or not self._controller:
            return False

        try:
            job = self._controller.post_start_app(package_name)
            job.wait()
            return job.succeeded
        except Exception as e:
            self.logger.warning(LogCategory.MAIN, f"启动应用失败：{package_name}, 错误：{e}")
            return False
    
    def stop_app(self, package_name: str) -> bool:
        """
        关闭应用
        
        Args:
            package_name: 应用包名
        
        Returns:
            bool: 是否关闭成功
        """
        if not self._connected or not self._controller:
            return False

        try:
            job = self._controller.post_stop_app(package_name)
            job.wait()
            return job.succeeded
        except Exception as e:
            self.logger.warning(LogCategory.MAIN, f"关闭应用失败：{package_name}, 错误：{e}")
            return False
    
    # ==================== 属性访问 ====================
    
    @property
    def connected(self) -> bool:
        """是否已连接"""
        return self._connected
    
    @property
    def tasker(self) -> Optional[Tasker]:
        """获取Tasker实例（用于Pipeline任务）"""
        return self._tasker
    
    @property
    def resource(self) -> Optional[Resource]:
        """获取Resource实例（用于加载Pipeline）"""
        return self._resource
    
    @property
    def controller(self) -> Optional[AdbController]:
        """获取Controller实例（用于单次控制）"""
        return self._controller