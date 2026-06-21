"""
屏幕捕获模块 - 负责设备屏幕截图和图像处理
优先使用 MAA Framework（通过 TouchManager），ADB 作为回退
"""
import base64
import io
import sys
import os
import subprocess
import time
from typing import Optional

from device.adb_manager import ADBDeviceManager
from core.logger import get_logger, LogCategory, LogLevel

try:
    from PIL import Image
except ImportError:
    print("警告: PIL库未安装，屏幕捕获功能将不可用")
    Image = None

try:
    import numpy as np
except ImportError:
    np = None

class ScreenCapture:
    """屏幕捕获器 - 优先 MAA，回退 ADB"""

    def __init__(self, adb_manager: ADBDeviceManager):
        self.adb_manager = adb_manager
        self.logger = get_logger()
        self.last_image_size = None
        self.last_capture_time = 0
        self.min_interval = 1.0
        self._touch_manager = None

    def set_touch_manager(self, touch_manager) -> None:
        """设置 TouchManager，启用 MAA 截屏（优先于 ADB）"""
        self._touch_manager = touch_manager

    def _capture_via_maa(self) -> Optional[bytes]:
        """通过 MAA Framework 截屏，返回 base64 编码的 PNG 字节"""
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
        """通过 ADB screencap 截屏，返回 base64 编码的 PNG 字节"""
        adb_path = getattr(self.adb_manager, 'adb_path', 'adb')
        cmd = [adb_path, "-s", device_serial, "exec-out", "screencap", "-p"]
        self.logger.debug(LogCategory.MAIN, "执行ADB截图命令", device_serial=device_serial)

        result = subprocess.run(cmd, capture_output=True, timeout=self.adb_manager.timeout)
        if result.returncode != 0:
            self.logger.exception(LogCategory.MAIN, "ADB截图命令执行异常",
                                  device_serial=device_serial, return_code=result.returncode)
            return None

        png_data = result.stdout
        if not png_data.startswith(b'\x89PNG\r\n\x1a\n'):
            self.logger.exception(LogCategory.MAIN, "PNG数据完整性验证异常",
                                  device_serial=device_serial, size_bytes=len(png_data))
            return None

        image = Image.open(io.BytesIO(png_data))
        return self._image_to_base64(image)
        
    def capture_screen(self, device_serial: str) -> Optional[bytes]:
        """捕获设备屏幕截图 —— 优先 MAA，回退 ADB"""
        if Image is None:
            self.logger.exception(LogCategory.MAIN, "PIL库未初始化")
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

        # 优先 MAA 截屏
        base64_data = self._capture_via_maa()
        method = "MAA"
        if base64_data is None:
            # 回退 ADB
            base64_data = self._capture_via_adb(device_serial)
            method = "ADB"

        if base64_data is None:
            return None

        total_duration_ms = (time.time() - start_time) * 1000
        self.logger.info(LogCategory.MAIN, f"屏幕捕获完成 ({method})",
                         device_serial=device_serial,
                         base64_length=len(base64_data),
                         total_duration_ms=round(total_duration_ms, 3))
        self.logger.log_performance("screen_capture", total_duration_ms, device_serial=device_serial)
        self.last_capture_time = time.time()
        return base64_data
            
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

        # 转换为RGB（如果需要）
        if image.mode != 'RGB':
            image = image.convert('RGB')

        return image
        
    def _image_to_base64(self, image) -> bytes:
        """将PIL图像转换为Base64编码的PNG"""
        start_time = time.time()
        
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        png_data = buffer.getvalue()
        base64_data = base64.b64encode(png_data)
        
        duration_ms = (time.time() - start_time) * 1000
        self.logger.log_performance("image_to_base64", duration_ms, format="PNG")
        
        return base64_data
        
    def get_device_info(self, device_serial: str) -> dict:
        """获取设备信息"""
        self.logger.debug(LogCategory.MAIN, "获取设备信息", device_serial=device_serial)
        resolution = self.adb_manager.get_device_resolution(device_serial)
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