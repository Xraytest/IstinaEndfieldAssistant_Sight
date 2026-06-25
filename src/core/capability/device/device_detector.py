"""
设备类型检测器 - 基于 StarRailCopilot 设计
自动识别模拟器类型并推荐最佳截图/触控配置
"""
import os
import sys
import socket
from typing import Optional, Tuple, Dict, Any
from enum import Enum
from dataclasses import dataclass

from core.foundation.paths import ensure_src_path
ensure_src_path(__file__)

from core.foundation.logger import get_logger, LogCategory

try:
    from adbutils import AdbClient
    ADBUTILS_AVAILABLE = True
except ImportError:
    ADBUTILS_AVAILABLE = False


class DeviceType(Enum):
    """设备类型枚举"""
    UNKNOWN = "unknown"
    MUMU = "mumu"           # MuMu模拟器
    LDPLAYER = "ldplayer"   # LDPlayer
    BLUESTACKS = "bluestacks"  # BlueStacks
    WSA = "wsa"             # Windows Subsystem for Android
    WAYDROID = "waydroid"   # Waydroid (Linux)
    AVD = "avd"             # Android Virtual Device
    REAL_DEVICE = "real"    # 真机
    EMULATOR = "emulator"   # 其他模拟器


@dataclass
class DeviceInfo:
    """设备信息数据结构"""
    serial: str
    device_type: DeviceType
    original_resolution: Tuple[int, int]  # 设备原始分辨率
    recommended_screenshot: str  # 推荐截图方法
    recommended_control: str      # 推荐触控方法
    properties: Dict[str, Any]    # 设备属性（getprop 查询结果）
    is_emulator: bool = False    # 是否为模拟器
    is_network_device: bool = False  # 是否为网络设备


class DeviceDetector:
    """
    设备类型检测器

    基于 ADB 属性查询和端口分析，自动识别设备类型并推荐配置
    参考自 StarRailCopilot 的 Connection 类设备检测逻辑
    """

    # 端口范围定义
    MUMU_PORT_RANGE = (16384, 17408)  # MuMu 12 端口范围
    BLUESTACKS_AIR_PORT_RANGE = (5555, 5875)  # BlueStacks Air (Mac)

    # 推荐配置映射
    RECOMMENDATIONS = {
        DeviceType.MUMU: {
            "screenshot": "scrcpy",
            "control": "MaaTouch"
        },
        DeviceType.LDPLAYER: {
            "screenshot": "ldopengl",
            "control": "MaaTouch"
        },
        DeviceType.BLUESTACKS: {
            "screenshot": "scrcpy",
            "control": "MaaTouch"
        },
        DeviceType.WSA: {
            "screenshot": "scrcpy",
            "control": "ADB"  # WSA 下 MaaTouch 可能有问题
        },
        DeviceType.WAYDROID: {
            "screenshot": "scrcpy",
            "control": "MaaTouch"
        },
        DeviceType.AVD: {
            "screenshot": "scrcpy",
            "control": "MaaTouch"
        },
        DeviceType.REAL_DEVICE: {
            "screenshot": "scrcpy",
            "control": "MaaTouch"
        },
        DeviceType.EMULATOR: {
            "screenshot": "auto",
            "control": "auto"
        },
        DeviceType.UNKNOWN: {
            "screenshot": "adb",
            "control": "ADB"
        }
    }

    def __init__(self, adb_manager):
        """
        初始化设备检测器

        Args:
            adb_manager: ADBDeviceManager 实例
        """
        self.adb_manager = adb_manager
        self.logger = get_logger()

    def detect_device_type(self, serial: str) -> DeviceType:
        """
        检测设备类型

        检测顺序（从最具体到最一般）：
        1. WSA: serial == 'wsa-0'
        2. BlueStacks Air: 端口 + Mac + Tiramisu64
        3. MuMu: 端口范围 + nemud 属性
        4. Waydroid: ro.product.brand 包含 'waydroid'
        5. AVD: 硬件特征 (ranchu, goldfish)
        6. 真机: 通过端口判断
        7. 其他模拟器: 通用模拟器特征

        Args:
            serial: 设备序列号

        Returns:
            DeviceType: 检测到的设备类型
        """
        self.logger.debug(LogCategory.MAIN, "开始检测设备类型", serial=serial)

        # 1. 检查 WSA
        if serial == 'wsa-0':
            self.logger.info(LogCategory.MAIN, "检测到 WSA 设备")
            return DeviceType.WSA

        # 提取端口号
        port = self._extract_port(serial)

        # 2. 检查 BlueStacks Air
        if self._is_bluestacks_air(port, serial):
            self.logger.info(LogCategory.MAIN, "检测到 BlueStacks Air", serial=serial)
            return DeviceType.BLUESTACKS

        # 3. 检查 MuMu
        if self._is_mumu_family(port, serial):
            self.logger.info(LogCategory.MAIN, "检测到 MuMu 模拟器", serial=serial)
            return DeviceType.MUMU

        # 4. 检查 Waydroid
        if self._is_waydroid(serial):
            self.logger.info(LogCategory.MAIN, "检测到 Waydroid", serial=serial)
            return DeviceType.WAYDROID

        # 5. 检查 AVD
        if self._is_avd(serial):
            self.logger.info(LogCategory.MAIN, "检测到 AVD", serial=serial)
            return DeviceType.AVD

        # 6. 判断真机 vs 模拟器
        is_emulator = self._is_emulator(serial, port)
        if is_emulator:
            self.logger.info(LogCategory.MAIN, "检测到通用模拟器", serial=serial)
            return DeviceType.EMULATOR
        else:
            self.logger.info(LogCategory.MAIN, "检测到真机", serial=serial)
            return DeviceType.REAL_DEVICE

    def get_device_info(self, serial: str, force_refresh: bool = False) -> Optional[DeviceInfo]:
        """
        获取完整设备信息（包含分辨率、推荐配置）

        Args:
            serial: 设备序列号
            force_refresh: 是否强制刷新属性缓存

        Returns:
            DeviceInfo: 设备信息对象，失败返回 None
        """
        try:
            # 检测设备类型
            device_type = self.detect_device_type(serial)

            # 获取设备原始分辨率
            resolution = self._get_device_resolution(serial)

            # 获取设备属性
            properties = self._collect_device_properties(serial, force_refresh)

            # 获取推荐配置
            recommendation = self.RECOMMENDATIONS.get(device_type, self.RECOMMENDATIONS[DeviceType.UNKNOWN])

            device_info = DeviceInfo(
                serial=serial,
                device_type=device_type,
                original_resolution=resolution,
                recommended_screenshot=recommendation["screenshot"],
                recommended_control=recommendation["control"],
                properties=properties,
                is_emulator=device_type in [DeviceType.MUMU, DeviceType.LDPLAYER, DeviceType.BLUESTACKS,
                                            DeviceType.WSA, DeviceType.WAYDROID, DeviceType.AVD, DeviceType.EMULATOR],
                is_network_device=':' in serial
            )

            self.logger.info(LogCategory.MAIN, "设备信息获取完成",
                            serial=serial,
                            type=device_type.value,
                            resolution=f"{resolution[0]}x{resolution[1]}",
                            screenshot=recommendation["screenshot"],
                            control=recommendation["control"])

            return device_info

        except Exception as e:
            self.logger.exception(LogCategory.MAIN, "获取设备信息失败", serial=serial, error=str(e))
            return None

    def _extract_port(self, serial: str) -> Optional[int]:
        """从序列号提取端口号"""
        if ':' in serial:
            try:
                return int(serial.split(':')[1])
            except (ValueError, IndexError):
                return None
        return None

    def _is_bluestacks_air(self, port: Optional[int], serial: str) -> bool:
        """检测是否为 BlueStacks Air"""
        if port is None:
            return False

        # 端口范围 5555-5875
        if not (5555 <= port <= 5875):
            return False

        # 必须查询设备属性确认
        try:
            images = self._getprop(serial, 'bst.installed_images')
            if images and 'Tiramisu64' in images:
                return True
        except Exception:
            pass

        return False

    def _is_mumu_family(self, port: Optional[int], serial: str) -> bool:
        """
        检测是否为 MuMu 模拟器

        MuMu 特征：
        - 端口范围 16384-17408 (MuMu 12) - 强特征
        - 属性 nemud.app_keep_alive 存在 - 辅助验证
        - 属性 nemud.player_version 存在 - 辅助验证
        """
        # 端口判断（强特征，符合即认为 MuMu）
        if port is not None and 16384 <= port <= 17408:
            return True

        # 序列号包含 "mumu" (不区分大小写)
        if 'mumu' in serial.lower():
            return True

        return False

    def _is_waydroid(self, serial: str) -> bool:
        """检测是否为 Waydroid"""
        try:
            brand = self._getprop(serial, 'ro.product.brand')
            if brand and 'waydroid' in brand.lower():
                return True
        except Exception:
            pass
        return False

    def _is_avd(self, serial: str) -> bool:
        """检测是否为 AVD (Android Virtual Device)"""
        try:
            # AVD 使用 "ranchu" 作为硬件名称
            hardware = self._getprop(serial, 'ro.hardware')
            if hardware and 'ranchu' in hardware.lower():
                return True

            # 某些 AVD 使用 goldfish
            audio_primary = self._getprop(serial, 'ro.hardware.audio.primary')
            if audio_primary and 'goldfish' in audio_primary.lower():
                return True
        except Exception:
            pass
        return False

    def _is_emulator(self, serial: str, port: Optional[int]) -> bool:
        """
        判断是否为模拟器（非特定类型）

        参考 StarRailCopilot 的 is_emulator 逻辑：
        - 网络设备且端口在常见模拟器范围 → 可能是模拟器
        - 真机通常使用 USB 连接（无端口）
        """
        # 如果有端口号，通常是模拟器或网络设备
        if port is not None:
            # 常见模拟器端口范围
            emulator_ports = [5555, 5554, 5562, 21503, 62001, 26000, 27000]
            if port in emulator_ports:
                return True
            # 高端口号 (>= 10000) 通常是模拟器
            if port >= 10000:
                return True

        # 查询 Build.Fingerprint 包含 "generic"
        try:
            fingerprint = self._getprop(serial, 'ro.build.fingerprint')
            if fingerprint and 'generic' in fingerprint.lower():
                return True
        except Exception:
            pass

        return False

    def _get_device_resolution(self, serial: str) -> Tuple[int, int]:
        """
        获取设备原始分辨率

        通过 ADB 命令: wm size

        Returns:
            (width, height) 元组，失败返回 (0, 0)
        """
        try:
            output = self.adb_manager.shell_command(
                serial,
                "wm size",
                timeout=5
            )[1].strip()

            # 输出格式: "Physical size: 1080x1920"
            if "Physical size:" in output:
                size_str = output.split("Physical size:")[1].strip()
                if 'x' in size_str:
                    width_str, height_str = size_str.split('x')
                    width, height = int(width_str), int(height_str)
                    self.logger.debug(LogCategory.MAIN, "获取设备分辨率成功",
                                    serial=serial,
                                    resolution=f"{width}x{height}")
                    return width, height

            # 备用: 尝试其他格式
            import re
            match = re.search(r'(\d+)x(\d+)', output)
            if match:
                width, height = int(match.group(1)), int(match.group(2))
                return width, height

        except Exception as e:
            self.logger.warning(LogCategory.MAIN, "获取分辨率失败", serial=serial, error=str(e))

        return 0, 0

    def _collect_device_properties(self, serial: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        收集设备关键属性

        Args:
            serial: 设备序列号
            force_refresh: 是否强制刷新（目前未实现缓存）

        Returns:
            属性字典
        """
        props = {}

        # 关键属性列表（按需查询）
        key_props = [
            'ro.product.brand',          # 品牌
            'ro.product.model',          # 型号
            'ro.build.version.sdk',      # SDK 版本
            'ro.hardware',               # 硬件
            'ro.product.cpu.abi',        # CPU 架构
            'nemud.app_keep_alive',      # MuMu 保活设置
            'nemud.player_version',      # MuMu 版本
            'nemud.player_engine',       # MuMu 引擎 (NEMUX/MACPRO)
            'bst.installed_images',      # BlueStacks 镜像
            'ro.build.fingerprint',      # 构建指纹
        ]

        for prop in key_props:
            try:
                value = self._getprop(serial, prop)
                if value:
                    props[prop] = value
            except Exception:
                pass

        return props

    def _getprop(self, serial: str, prop_name: str) -> str:
        """执行 getprop 命令获取属性值"""
        try:
            return self.adb_manager.shell_command(
                serial,
                f"getprop {prop_name}",
                timeout=5
            )[1].strip()
        except Exception as e:
            self.logger.debug(LogCategory.MAIN, "getprop 失败", prop=prop_name, error=str(e))
            return ""

    def get_recommended_config(self, device_info: DeviceInfo) -> Dict[str, Any]:
        """
        根据设备信息返回推荐的配置字典

        Args:
            device_info: 设备信息对象

        Returns:
            推荐配置字典，结构:
            {
                "screenshot": {
                    "method": "scrcpy|nemu_ipc|ldopengl|adb",
                    "config": {...}  # 方法特定配置
                },
                "control": {
                    "method": "MaaTouch|minitouch|scrcpy|ADB",
                    "config": {...}
                }
            }
        """
        rec = self.RECOMMENDATIONS.get(device_info.device_type, self.RECOMMENDATIONS[DeviceType.UNKNOWN])

        config = {
            "screenshot": {
                "method": rec["screenshot"],
                "config": self._get_screenshot_config(rec["screenshot"], device_info)
            },
            "control": {
                "method": rec["control"],
                "config": self._get_control_config(rec["control"], device_info)
            }
        }

        self.logger.debug(LogCategory.MAIN, "推荐配置生成完成",
                        device_type=device_info.device_type.value,
                        screenshot=rec["screenshot"],
                        control=rec["control"])

        return config

    def _get_screenshot_config(self, method: str, device_info: DeviceInfo) -> Dict[str, Any]:
        """获取截图方法的具体配置"""
        base_config = {
            "min_interval": 0.1,
            "use_original_resolution": True
        }

        if method == "scrcpy":
            base_config.update({
                "frame_rate": 10,
                "max_resolution": 1280,
                "bitrate": 20000000,
                "auto_restart": True
            })
        elif method == "nemu_ipc":
            base_config.update({
                "buffer_size": 4096
            })
        elif method == "ldopengl":
            base_config.update({
                "buffer_size": 4096
            })
        elif method == "droidcast":
            base_config.update({
                "max_fps": 30
            })

        return base_config

    def _get_control_config(self, method: str, device_info: DeviceInfo) -> Dict[str, Any]:
        """获取触控方法的具体配置"""
        base_config = {
            "press_duration_ms": 50,
            "press_jitter_px": 2,
            "swipe_delay_min_ms": 100,
            "swipe_delay_max_ms": 300,
            "use_normalized_coords": True
        }

        if method == "MaaTouch":
            base_config.update({
                "input_methods": 3,  # MaaAdbInputMethodEnum.MaaTouch
                "screencap_methods": 0,  # Default
                "auto_restart": True
            })
        elif method == "minitouch":
            base_config.update({
                "port": 1111  # minitouch 默认端口
            })
        elif method == "scrcpy":
            base_config.update({
                "use_scrcpy_control": True
            })

        return base_config


# 便捷函数
def detect_device(adb_manager, serial: str) -> Optional[DeviceInfo]:
    """
    快速检测设备

    Args:
        adb_manager: ADBDeviceManager 实例
        serial: 设备序列号

    Returns:
        DeviceInfo 或 None
    """
    detector = DeviceDetector(adb_manager)
    return detector.get_device_info(serial)