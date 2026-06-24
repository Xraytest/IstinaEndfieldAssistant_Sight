"""
StarRailCopilot 截图方法集 - 移植与适配
包含 7 种截图方式：ADB, scrcpy, nemu_ipc, ldopengl, DroidCast, aScreenCap, uiautomator2

注意：此类设计为 Mixin，需配合 ADBDeviceManager 和 logger 使用
"""
import os
import sys
import time
import subprocess
import socket
from io import BytesIO
from typing import Optional, Tuple, Any
from functools import wraps

import numpy as np
import cv2
from PIL import Image

from core.foundation.paths import ensure_src_path
ensure_src_path(__file__)

from core.foundation.logger import get_logger, LogCategory
from .retry import retry, RETRY_TRIES

try:
    from adbutils import AdbError, AdbConnection, Network as AdbNetwork
    ADBUTILS_AVAILABLE = True
except ImportError:
    ADBUTILS_AVAILABLE = False
    AdbError = None
    AdbConnection = None

try:
    from av.codec import CodecContext
    from av.error import InvalidDataError
    PYAV_AVAILABLE = True
except ImportError:
    PYAV_AVAILABLE = False


class ImageTruncated(Exception):
    """图像数据不完整异常"""
    pass


class StarRailScreenshotMixin:
    """
    StarRailCopilot 截图方法 Mixin

    需在宿主类中提供：
    - self.adb_manager: ADBDeviceManager 实例
    - self.config: 配置对象（支持 dict 访问）
    - self.logger: 日志器
    - self.device_serial: 设备序列号
    """

    # ==================== 公共接口 ====================

    def screenshot_adb(self) -> np.ndarray:
        """ADB 截图（使用 exec-out）"""
        return self._screenshot_adb_impl(use_nc=False)

    def screenshot_adb_nc(self) -> np.ndarray:
        """ADB 截图（使用 netcat）"""
        return self._screenshot_adb_impl(use_nc=True)

    def screenshot_uiautomator2(self) -> np.ndarray:
        """uiautomator2 截图（需要 minicap）"""
        # 简化实现：回退到 ADB
        self.logger.warning(LogCategory.MAIN, "uiautomator2 截图未实现，回退到 ADB")
        return self.screenshot_adb()

    def screenshot_ascreencap(self) -> np.ndarray:
        """aScreenCap 截图"""
        # 简化实现：回退到 ADB
        self.logger.warning(LogCategory.MAIN, "aScreenCap 截图未实现，回退到 ADB")
        return self.screenshot_adb()

    def screenshot_ascreencap_nc(self) -> np.ndarray:
        """aScreenCap 截图（netcat）"""
        # 简化实现：回退到 ADB nc
        self.logger.warning(LogCategory.MAIN, "aScreenCap_nc 截图未实现，回退到 ADB nc")
        return self.screenshot_adb_nc()

    def screenshot_droidcast(self) -> np.ndarray:
        """DroidCast 截图"""
        # 简化实现：回退到 ADB
        self.logger.warning(LogCategory.MAIN, "DroidCast 截图未实现，回退到 ADB")
        return self.screenshot_adb()

    def screenshot_droidcast_raw(self) -> np.ndarray:
        """DroidCast 原始截图"""
        # 简化实现：回退到 ADB
        self.logger.warning(LogCategory.MAIN, "DroidCast_raw 截图未实现，回退到 ADB")
        return self.screenshot_adb()

    def screenshot_scrcpy(self) -> np.ndarray:
        """
        scrcpy 视频流截图

        注意：需要先启动 scrcpy server（通过 ScrcpyCore 类管理）
        此处仅用于接口兼容，实际由 ScreenCapture 管理 scrcpy 核心
        """
        raise NotImplementedError("scrcpy 截图应由 ScrcpyCore 管理，此处仅作接口占位")

    def screenshot_nemu_ipc(self) -> np.ndarray:
        """MuMu IPC 共享内存截图"""
        # 简化实现：回退到 ADB
        self.logger.warning(LogCategory.MAIN, "nemu_ipc 截图未实现，回退到 ADB")
        return self.screenshot_adb()

    def screenshot_ldopengl(self) -> np.ndarray:
        """LDPlayer OpenGL 截图"""
        # 简化实现：回退到 ADB
        self.logger.warning(LogCategory.MAIN, "ldopengl 截图未实现，回退到 ADB")
        return self.screenshot_adb()

    # ==================== 内部实现 ====================

    @retry
    def _screenshot_adb_impl(self, use_nc: bool = False) -> np.ndarray:
        """
        ADB 截图核心实现

        Args:
            use_nc: 是否使用 netcat（更稳定但需要设备支持）

        Returns:
            np.ndarray: BGR 格式图像
        """
        serial = getattr(self, 'device_serial', '')
        adb_path = self.adb_manager.adb_path

        if use_nc:
            # 使用 netcat（需要设备有 nc 命令）
            return self._screenshot_adb_nc_impl(adb_path, serial)
        else:
            # 使用 exec-out（标准方法）
            return self._screenshot_adb_exec_out_impl(adb_path, serial)

    def _screenshot_adb_exec_out_impl(self, adb_path: str, serial: str) -> np.ndarray:
        """ADB exec-out 截图实现"""
        cmd = [adb_path, "-s", serial, "exec-out", "screencap", "-p"]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=self.adb_manager.timeout
            )

            if result.returncode != 0:
                raise AdbError(f"ADB 截图失败: {result.stderr.decode('utf-8', errors='ignore')}")

            png_data = result.stdout

            # 验证 PNG 头部
            if not png_data.startswith(b'\x89PNG\r\n\x1a\n'):
                raise ImageTruncated("PNG 数据头部校验失败")

            # 解码图像
            image = cv2.imdecode(np.frombuffer(png_data, np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise ImageTruncated("cv2.imdecode 返回 None")

            return image

        except subprocess.TimeoutExpired:
            raise AdbError("ADB 截图超时")
        except Exception as e:
            raise AdbError(f"ADB 截图异常: {e}") from e

    def _screenshot_adb_nc_impl(self, adb_path: str, serial: str) -> np.ndarray:
        """ADB netcat 截图实现（通过反向服务器）"""
        # 简化：暂时不支持 nc，回退到 exec-out
        self.logger.debug(LogCategory.MAIN, "nc 模式暂未完全实现，使用 exec-out 替代")
        return self._screenshot_adb_exec_out_impl(adb_path, serial)

    def _screenshot_adb_exec_out_impl(self, adb_path: str, serial: str) -> np.ndarray:
        """ADB exec-out 截图实现"""
        cmd = [adb_path, "-s", serial, "exec-out", "screencap", "-p"]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=self.adb_manager.timeout
            )

            if result.returncode != 0:
                raise AdbError(f"ADB 截图失败: {result.stderr.decode('utf-8', errors='ignore')}")

            png_data = result.stdout

            # 验证 PNG 头部
            if not png_data.startswith(b'\x89PNG\r\n\x1a\n'):
                raise ImageTruncated("PNG 数据头部校验失败")

            # 解码图像
            image = cv2.imdecode(np.frombuffer(png_data, np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise ImageTruncated("cv2.imdecode 返回 None")

            return image

        except subprocess.TimeoutExpired:
            raise AdbError("ADB 截图超时")
        except Exception as e:
            raise AdbError(f"ADB 截图异常: {e}") from e

    def _screenshot_adb_nc_impl(self, adb_path: str, serial: str) -> np.ndarray:
        """ADB netcat 截图实现（通过反向服务器）"""
        # 简化：暂时不支持 nc，回退到 exec-out
        self.logger.debug(LogCategory.MAIN, "nc 模式暂未完全实现，使用 exec-out 替代")
        return self._screenshot_adb_exec_out_impl(adb_path, serial)

    # ==================== 工具方法 ====================

    def _handle_orientated_image(self, image: np.ndarray) -> np.ndarray:
        """
        处理设备方向（旋转图像到横屏）

        Args:
            image: 原始图像

        Returns:
            处理后的图像
        """
        # 获取设备方向（需在宿主类中实现 get_orientation）
        try:
            orientation = getattr(self, 'get_orientation', lambda: 0)()
        except Exception:
            orientation = 0

        width, height = image.shape[1], image.shape[0]

        # 1280x720 不需要旋转
        if width == 1280 and height == 720:
            return image

        # 根据方向旋转
        if orientation == 0:
            pass
        elif orientation == 1:
            image = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
        elif orientation == 2:
            image = cv2.rotate(image, cv2.ROTATE_180)
        elif orientation == 3:
            image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        else:
            raise ValueError(f"无效的设备方向: {orientation}")

        return image


# 便捷函数：加载 PNG 数据
def load_screencap(data: bytes) -> np.ndarray:
    """
    从 screencap 原始数据加载图像

    Args:
        data: screencap 输出的原始字节

    Returns:
        np.ndarray: BGR 图像
    """
    if len(data) < 500:
        raise ImageTruncated(f"数据太小: {len(data)} bytes")

    # 尝试多种加载方式（参考 StarRailCopilot）
    for method in range(3):
        try:
            if method == 0:
                # 原始数据直接解码
                image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            elif method == 1:
                # 替换换行符
                data_fixed = data.replace(b'\r\n', b'\n')
                image = cv2.imdecode(np.frombuffer(data_fixed, np.uint8), cv2.IMREAD_COLOR)
            else:
                # 双重换行符替换
                data_fixed = data.replace(b'\r\r\n', b'\n')
                image = cv2.imdecode(np.frombuffer(data_fixed, np.uint8), cv2.IMREAD_COLOR)

            if image is not None:
                return image
        except Exception:
            continue

    raise ImageTruncated("所有解码方法均失败")