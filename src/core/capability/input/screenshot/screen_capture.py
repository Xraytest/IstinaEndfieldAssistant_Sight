"""
屏幕捕获模块 - 负责设备屏幕截图和图像处理
优先使用 scrcpy 视频流，MAA/ADB 作为可选回退
"""
import base64
import io
import sys
import os
import subprocess
import time
from typing import Optional, Dict, Tuple, Any, List
from core.foundation.paths import ensure_src_path
ensure_src_path(__file__)

from core.capability.device.adb_manager import ADBDeviceManager
from core.foundation.logger import get_logger, LogCategory, LogLevel
from core.capability.device.stuck_detector import StuckDetector, ErrorHandler

try:
    from PIL import Image
except ImportError:
    print("警告：PIL 库未安装，屏幕捕获功能将不可用")
    Image = None

try:
    import numpy as np
except ImportError:
    np = None

# 可选导入 scrcpy
try:
    from .scrcpy_core import ScrcpyCore, ScrcpyError
    SCRCPY_AVAILABLE = True
except ImportError:
    SCRCPY_AVAILABLE = False
    ScrcpyCore = None
    ScrcpyError = Exception

class ScreenCapture:
    """
    屏幕捕获器 - 优先 scrcpy 视频流，可选回退到 MAA/ADB

    配置选项（通过 config 参数）：
    - screen.method: 'auto'/'scrcpy'/'maa'/'adb'（默认 'auto'）
    - screen.scrcpy/frame_rate: 帧率（默认 10）
    - screen.scrcpy/max_resolution: 最大分辨率（默认 1280）
    - screen.scrcpy/bitrate: 码率（默认 20000000）
    - screen.scrcpy/auto_restart: 自动重启（默认 true）
    - screen/use_original_resolution: 保持原始分辨率（默认 true）
    """

    def __init__(self, adb_manager: ADBDeviceManager, config: dict = None):
        """
        初始化屏幕捕获器

        Args:
            adb_manager: ADB 设备管理器
            config: 配置字典，包含 screenshot 相关设置
        """
        self.adb_manager = adb_manager
        self.config = config or {}
        self.logger = get_logger()

        # 截图间隔控制
        self.last_image_size = None
        self.last_capture_time = 0
        self.min_interval = self.config.get('min_interval', 0.1)  # 默认 100ms

        # MAA TouchManager（可选）
        self._touch_manager = None

        # scrcpy 核心
        self._scrcpy_core: Optional[ScrcpyCore] = None
        self._scrcpy_enabled = self._determine_scrcpy_enabled()
        self._scrcpy_device_serial = None  # 延迟初始化

        # 设备检测器（用于智能选择截图方法）
        self._device_detector = None
        self._device_cache = {}  # 缓存设备信息

        # 错误处理与卡死检测
        self._stuck_detector = StuckDetector(
            stuck_timeout=60.0,
            click_history_size=30,
            max_clicks_in_15=12
        )
        self._error_handler = ErrorHandler(self.logger, max_retries=5)

    def set_touch_manager(self, touch_manager) -> None:
        """设置 TouchManager，启用 MAA 截屏（作为回退方案）"""
        self._touch_manager = touch_manager

    def _get_device_detector(self):
        """获取设备检测器（延迟初始化）"""
        if self._device_detector is None:
            from core.capability.device.device_detector import DeviceDetector
            self._device_detector = DeviceDetector(self.adb_manager)
        return self._device_detector

    def _get_device_info(self, serial: str) -> Optional[Dict]:
        """获取设备信息（带缓存）"""
        if serial not in self._device_cache:
            try:
                detector = self._get_device_detector()
                device_info = detector.get_device_info(serial)
                if device_info:
                    self._device_cache[serial] = {
                        "type": device_info.device_type.value,
                        "original_resolution": device_info.original_resolution,
                        "recommended_screenshot": device_info.recommended_screenshot,
                        "recommended_control": device_info.recommended_control,
                        "properties": device_info.properties
                    }
            except Exception as e:
                self.logger.warning(LogCategory.MAIN, "设备信息获取失败", serial=serial, error=str(e))
                self._device_cache[serial] = None

        return self._device_cache.get(serial)

    def _determine_scrcpy_enabled(self) -> bool:
        """
        根据配置决定是否启用 scrcpy（已废弃，保留用于兼容）

        Returns:
            bool: 是否启用 scrcpy
        """
        # 旧的逻辑：仅检查配置
        if not SCRCPY_AVAILABLE:
            return False

        method = self.config.get('screen', {}).get('method', 'auto')
        if method == 'scrcpy':
            return True
        elif method == 'auto':
            return True
        elif method in ('maa', 'adb'):
            return False

        return True

    def _capture_via_maa_fallback(self) -> Optional[bytes]:
        """通过 MAA Framework 截屏（回退方案），返回 base64 编码的 PNG 字节"""
        if self._touch_manager is None or not self._touch_manager.connected:
            return None
        if np is None or Image is None:
            return None

        img = self._touch_manager.screencap()
        if img is None:
            return None

        # MAA 返回 numpy BGR → RGB → PIL → PNG → base64
        img_rgb = img[:, :, ::-1]  # BGR → RGB
        pil_image = Image.fromarray(img_rgb)
        return self._image_to_base64(pil_image)

    def _capture_via_adb(self, device_serial: str) -> Optional[bytes]:
        """通过 ADB screencap 截屏（回退方案），返回 base64 编码的 PNG 字节"""
        adb_path = getattr(self.adb_manager, 'adb_path', 'adb')
        cmd = [adb_path, "-s", device_serial, "exec-out", "screencap", "-p"]
        self.logger.debug(LogCategory.MAIN, "执行 ADB 截图命令", device_serial=device_serial)

        result = subprocess.run(cmd, capture_output=True, timeout=self.adb_manager.timeout)
        if result.returncode != 0:
            self.logger.exception(LogCategory.MAIN, "ADB 截图命令执行异常",
                                  device_serial=device_serial, return_code=result.returncode)
            return None

        png_data = result.stdout
        if not png_data.startswith(b'\x89PNG\r\n\x1a\n'):
            self.logger.exception(LogCategory.MAIN, "PNG 数据完整性验证异常",
                                  device_serial=device_serial, size_bytes=len(png_data))
            return None

        image = Image.open(io.BytesIO(png_data))
        return self._image_to_base64(image)

    # ==================== scrcpy 方法 ====================

    def _ensure_scrcpy_started(self, device_serial: str) -> None:
        """
        确保 scrcpy 已启动（延迟初始化）

        Args:
            device_serial: 设备序列号

        Raises:
            ScrcpyError: scrcpy 启动失败
        """
        if self._scrcpy_core is not None and self._scrcpy_core.is_alive():
            return  # 已启动且运行中

        # 如果已有实例但已停止，清理
        if self._scrcpy_core is not None:
            self._scrcpy_core.stop()
            self._scrcpy_core = None

        # 创建并启动新的 scrcpy 核心
        self.logger.info(LogCategory.MAIN, "启动 scrcpy 视频流", device_serial=device_serial)

        scrcpy_config = self.config.get('screen', {}).get('scrcpy', {})
        self._scrcpy_core = ScrcpyCore(
            self.adb_manager,
            device_serial,
            config=scrcpy_config
        )

        try:
            self._scrcpy_core.start()
            self._scrcpy_device_serial = device_serial
            self.logger.info(LogCategory.MAIN, "scrcpy 视频流已启动",
                             device_serial=device_serial,
                             resolution=f"{self._scrcpy_core.get_resolution()[0]}x{self._scrcpy_core.get_resolution()[1]}")
        except Exception as e:
            self._scrcpy_core = None
            raise ScrcpyError(f"scrcpy 启动失败: {e}") from e

    def _capture_via_scrcpy(self, device_serial: str) -> Optional[bytes]:
        """
        通过 scrcpy 视频流截屏（带错误处理）

        Args:
            device_serial: 设备序列号

        Returns:
            base64 编码的 PNG 字节，或 None（失败）
        """
        if not SCRCPY_AVAILABLE or ScrcpyCore is None:
            self.logger.warning(LogCategory.MAIN, "scrcpy 不可用，跳过", device_serial=device_serial)
            return None

        try:
            # 确保 scrcpy 已启动
            self._ensure_scrcpy_started(device_serial)

            # 获取最新帧
            frame = self._scrcpy_core.get_latest_frame()
            if frame is None:
                self.logger.warning(LogCategory.MAIN, "scrcpy 无可用帧", device_serial=device_serial)
                return None

            # 将 numpy 数组转换为 PIL Image
            # frame 是 RGB 格式的 numpy.ndarray
            pil_image = Image.fromarray(frame)

            # 转换为 base64
            return self._image_to_base64(pil_image)

        except ScrcpyError as e:
            self.logger.error(LogCategory.MAIN, "scrcpy 截图失败", device_serial=device_serial, error=str(e))
            # scrcpy 失败时停止核心，由上层决定是否回退
            if self._scrcpy_core:
                self._scrcpy_core.stop()
                self._scrcpy_core = None
            return None
        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "scrcpy 截图异常", device_serial=device_serial, error=str(e))
            # 使用错误处理器决定是否重试
            if self._error_handler.should_retry(e, attempt=0):
                self.logger.info(LogCategory.MAIN, "scrcpy 截图异常将重试")
            return None

    def start_scrcpy(self, device_serial: str) -> bool:
        """
        手动启动 scrcpy 视频流

        Args:
            device_serial: 设备序列号

        Returns:
            bool: 是否启动成功
        """
        try:
            self._ensure_scrcpy_started(device_serial)
            return True
        except ScrcpyError as e:
            self.logger.error(LogCategory.MAIN, "手动启动 scrcpy 失败", device_serial=device_serial, error=str(e))
            return False

    def stop_scrcpy(self) -> None:
        """停止 scrcpy 视频流"""
        if self._scrcpy_core is not None:
            try:
                self._scrcpy_core.stop()
                self.logger.info(LogCategory.MAIN, "scrcpy 已停止")
            except Exception as e:
                self.logger.error(LogCategory.MAIN, "停止 scrcpy 失败", error=str(e))
            finally:
                self._scrcpy_core = None

    def release(self) -> None:
        """
        释放资源（应在销毁前调用）
        """
        self.stop_scrcpy()

    def _select_screenshot_method(self, device_serial: str) -> Tuple[str, Dict]:
        """
        智能选择截图方法

        选择策略：
        1. 如果配置指定了具体方法（非 auto），直接使用
        2. auto 模式：查询设备检测器推荐方案
        3. 考虑依赖可用性（scrcpy、MAA 等）
        4. 返回方法名和配置

        Returns:
            (method_name, config_dict)
        """
        config_screen = self.config.get('screen', {})
        method = config_screen.get('method', 'auto')

        # 非 auto 模式，直接返回配置的方法
        if method != 'auto':
            self.logger.debug(LogCategory.MAIN, "使用配置指定的截图方法",
                            device_serial=device_serial, method=method)
            return method, config_screen.get(method, {})

        # auto 模式：查询设备推荐
        device_info = self._get_device_info(device_serial)
        if device_info:
            recommended = device_info.get('recommended_screenshot', 'scrcpy')
            self.logger.info(LogCategory.MAIN, "auto 模式使用设备推荐方法",
                            device_serial=device_serial,
                            device_type=device_info.get('type'),
                            recommended=recommended)
            return recommended, config_screen.get(recommended, {})
        else:
            # 无法获取设备信息，回退到 scrcpy（如果可用）
            if self._scrcpy_enabled:
                self.logger.info(LogCategory.MAIN, "auto 模式使用默认 scrcpy",
                                device_serial=device_serial)
                return 'scrcpy', config_screen.get('scrcpy', {})
            else:
                self.logger.warning(LogCategory.MAIN, "auto 模式无可用方法，使用 ADB",
                                   device_serial=device_serial)
                return 'adb', {}

    def _capture_with_fallback(self, device_serial: str, primary_method: str, method_config: Dict) -> Optional[bytes]:
        """
        带自动降级的截图

        降级顺序（按优先级）：
        - 如果 primary_method 是 scrcpy: scrcpy → MAA → ADB
        - 如果 primary_method 是 ADB: ADB（无降级）
        - 其他：primary_method → ADB

        Args:
            device_serial: 设备序列号
            primary_method: 首选方法
            method_config: 方法配置

        Returns:
            base64 编码的 PNG 字节，或 None（全部失败）
        """
        # 定义降级链
        fallback_chain = {
            'scrcpy': ['scrcpy', 'maa', 'adb'],
            'nemu_ipc': ['nemu_ipc', 'scrcpy', 'maa', 'adb'],
            'ldopengl': ['ldopengl', 'scrcpy', 'maa', 'adb'],
            'droidcast': ['droidcast', 'scrcpy', 'maa', 'adb'],
            'adb': ['adb'],
            'maa': ['maa', 'adb']
        }

        chain = fallback_chain.get(primary_method, [primary_method, 'adb'])

        for i, method in enumerate(chain):
            try:
                self.logger.info(LogCategory.MAIN, f"尝试截图方法 ({i+1}/{len(chain)})",
                                device_serial=device_serial, method=method)

                base64_data = None
                if method == 'scrcpy':
                    base64_data = self._capture_via_scrcpy(device_serial)
                elif method == 'maa':
                    base64_data = self._capture_via_maa_fallback()
                elif method == 'adb':
                    base64_data = self._capture_via_adb(device_serial)
                elif method in ('nemu_ipc', 'ldopengl', 'droidcast', 'ascreencap'):
                    # 这些方法尚未完全实现，暂时回退
                    self.logger.warning(LogCategory.MAIN, f"{method} 方法未实现，跳过",
                                       device_serial=device_serial)
                    continue
                else:
                    self.logger.error(LogCategory.MAIN, "未知的截图方法", method=method)
                    continue

                if base64_data is not None:
                    if i > 0:
                        # 降级成功，记录日志
                        self.logger.warning(LogCategory.MAIN, f"截图方法降级: {primary_method} → {method}",
                                           device_serial=device_serial)
                    return base64_data

            except Exception as e:
                self.logger.warning(LogCategory.MAIN, f"截图方法 {method} 失败",
                                   device_serial=device_serial, error=str(e))
                # 继续尝试下一个方法
                continue

        self.logger.error(LogCategory.MAIN, "所有截图方法均失败", device_serial=device_serial)
        return None

    def capture_screen(self, device_serial: str) -> Optional[bytes]:
        """
        捕获设备屏幕截图 —— 智能选择方法，支持自动降级

        Returns:
            bytes: base64 编码的 PNG 图像，失败返回 None
        """
        if Image is None:
            self.logger.exception(LogCategory.MAIN, "PIL 库未初始化")
            return None

        current_time = time.time()
        time_since_last = current_time - self.last_capture_time
        if time_since_last < self.min_interval:
            wait_time = self.min_interval - time_since_last
            self.logger.debug(LogCategory.MAIN, f"截图间隔不足，等待 {wait_time:.3f} 秒",
                              device_serial=device_serial)
            time.sleep(wait_time)
            current_time = time.time()

        start_time = current_time

        # 智能选择截图方法
        primary_method, method_config = self._select_screenshot_method(device_serial)

        # 尝试截图（支持降级）
        base64_data = self._capture_with_fallback(device_serial, primary_method, method_config)
        if base64_data is None:
            self.logger.error(LogCategory.MAIN, "屏幕捕获失败（所有方法）", device_serial=device_serial)
            return None

        total_duration_ms = (time.time() - start_time) * 1000
        self.logger.info(LogCategory.MAIN, f"屏幕捕获完成",
                         device_serial=device_serial,
                         method=primary_method,
                         base64_length=len(base64_data),
                         total_duration_ms=round(total_duration_ms, 3))
        self.logger.log_performance("screen_capture", total_duration_ms, device_serial=device_serial)
        self.last_capture_time = time.time()
        return base64_data

    def __del__(self):
        """析构时释放资源"""
        self.release()

    def _process_image(self, image):
        """处理图像 - 不再缩放，保持原始分辨率以支持归一化坐标"""
        start_time = time.time()
        original_size = image.size

        # 2026-03-07: 删除图像缩放逻辑，使用原始图像进行归一化坐标处理
        # 不再调整图像大小，直接使用原始分辨率
        self.logger.debug(LogCategory.MAIN, "跳过图像尺寸调整",
                       original_size=f"{original_size[0]}x{original_size[1]}",
                       reason="使用归一化坐标，保持原始分辨率")

        duration_ms = (time.time() - start_time) * 1000
        self.logger.log_performance("image_process", duration_ms)

        # 转换为 RGB（如果需要）
        if image.mode != 'RGB':
            image = image.convert('RGB')

        return image

    def _image_to_base64(self, image) -> bytes:
        """将 PIL 图像转换为 Base64 编码的 PNG"""
        start_time = time.time()

        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        png_data = buffer.getvalue()
        base64_data = base64.b64encode(png_data)

        duration_ms = (time.time() - start_time) * 1000
        self.logger.log_performance("image_to_base64", duration_ms, format="PNG")

        return base64_data

    def get_device_info(self, device_serial: str) -> dict:
        """获取设备信息（优先从 scrcpy 获取分辨率）"""
        self.logger.debug(LogCategory.MAIN, "获取设备信息", device_serial=device_serial)

        # 尝试从 scrcpy 获取分辨率
        resolution = None
        if self._scrcpy_core and self._scrcpy_core.is_alive():
            resolution = self._scrcpy_core.get_resolution()
            self.logger.debug(LogCategory.MAIN, "使用 scrcpy 分辨率", resolution=resolution)

        # 回退到 ADB 查询
        if resolution is None or resolution == (0, 0):
            resolution = self.adb_manager.get_device_resolution(device_serial)
            self.logger.debug(LogCategory.MAIN, "使用 ADB 查询分辨率", resolution=resolution)

        model = self.adb_manager.get_device_model(device_serial)

        device_info = {
            'resolution': list(resolution) if resolution else [0, 0],
            'model': model,
            'image_size': list(self.last_image_size) if self.last_image_size else None
        }

        self.logger.debug(LogCategory.MAIN, "设备信息获取完成",
                        device_serial=device_serial,
                        resolution=device_info['resolution'],
                        model=model,
                        image_size=device_info['image_size'])

        return device_info
