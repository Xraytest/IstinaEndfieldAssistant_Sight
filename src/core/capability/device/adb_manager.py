"""
ADB设备管理器 - 管理Android设备的ADB连接
"""
import subprocess
import time
import os
import socket
from typing import List, Optional, Tuple, Dict, Any

from core.foundation.paths import ensure_src_path
ensure_src_path(__file__)
from core.foundation.logger import get_logger, LogCategory, LogLevel

try:
    from adbutils import AdbClient, AdbError, Network as AdbNetwork
    ADBUTILS_AVAILABLE = True
except ImportError:
    ADBUTILS_AVAILABLE = False
    AdbClient = None
    AdbError = None
    AdbNetwork = None


class AdbDeviceInfo:
    """ADB设备信息"""
    def __init__(self, serial: str, status: str, address: str = ""):
        self.serial = serial
        self.status = status
        self.address = address

    def __repr__(self):
        return f"AdbDeviceInfo(serial={self.serial}, status={self.status}, address={self.address})"


class ADBDeviceManager:
    """ADB设备管理器"""

    def __init__(self, adb_path: str, timeout: int = 10):
        """
        初始化ADB设备管理器

        Args:
            adb_path: ADB可执行文件路径
            timeout: 命令执行超时时间（秒）
        """
        self.adb_path = adb_path
        self.timeout = timeout
        self.logger = get_logger()
        self._connected_devices: Dict[str, AdbDeviceInfo] = {}

        # 设备连接状态跟踪
        self._last_connected_device: Optional[str] = None
        self._current_device: Optional[str] = None

        # 初始化 adbutils 客户端（用于 scrcpy 的 socket 连接）
        self._adb_client: Optional[AdbClient] = None
        if ADBUTILS_AVAILABLE:
            try:
                self._adb_client = AdbClient(host="127.0.0.1", port=5037)
                self.logger.debug(LogCategory.ADB, "adbutils 客户端初始化成功")
            except Exception as e:
                self.logger.warning(LogCategory.ADB, "adbutils 客户端初始化失败", error=str(e))
                self._adb_client = None
        else:
            self.logger.warning(LogCategory.ADB, "adbutils 未安装，scrcpy 功能将不可用")

        # 设备检测器（延迟初始化）
        self._detector = None
        
    def start_server(self) -> bool:
        """启动ADB服务器"""
        try:
            result = subprocess.run(
                [self.adb_path, "start-server"],
                capture_output=True,
                timeout=self.timeout,
                encoding='utf-8',
                errors='ignore'
            )
            if result.returncode == 0:
                self.logger.info(LogCategory.ADB, "ADB服务器启动成功")
                return True
            else:
                self.logger.exception(LogCategory.ADB, "ADB服务器启动失败",
                                     return_code=result.returncode,
                                     stderr=result.stderr or "")
                return False
        except subprocess.TimeoutExpired:
            self.logger.exception(LogCategory.ADB, "ADB服务器启动超时")
            return False
        except Exception as e:
            self.logger.exception(LogCategory.ADB, "ADB服务器启动异常", error=str(e))
            return False
    
    def kill_server(self) -> bool:
        """终止ADB服务器"""
        try:
            result = subprocess.run(
                [self.adb_path, "kill-server"],
                capture_output=True,
                timeout=self.timeout,
                encoding='utf-8',
                errors='ignore'
            )
            self.logger.info(LogCategory.ADB, "ADB服务器已终止")
            return True
        except Exception as e:
            self.logger.exception(LogCategory.ADB, "ADB服务器终止异常", error=str(e))
            return False
    
    def get_devices(self) -> List[AdbDeviceInfo]:
        """
        获取已连接的设备列表
        
        Returns:
            List[AdbDeviceInfo]: 设备信息列表
        """
        try:
            result = subprocess.run(
                [self.adb_path, "devices"],
                capture_output=True,
                timeout=self.timeout,
                encoding='utf-8',
                errors='ignore'
            )
            
            devices = []
            self._connected_devices.clear()  # 清空旧状态
            lines = result.stdout.strip().split('\n')
            for line in lines[1:]:  # 跳过标题行
                if '\t' in line:
                    serial, status = line.split('\t')
                    address = ""
                    if ':' in serial:  # 网络设备
                        address = serial
                    device_info = AdbDeviceInfo(serial, status, address)
                    devices.append(device_info)
                    # 跟踪已连接的设备（状态为 device）
                    if status == 'device':
                        self._connected_devices[serial] = device_info

            self.logger.debug(LogCategory.ADB, f"发现 {len(devices)} 个设备")
            return devices
            
        except Exception as e:
            self.logger.exception(LogCategory.ADB, "获取设备列表异常", error=str(e))
            return []
    
    def connect_device(self, address: str) -> bool:
        """
        连接网络设备

        Args:
            address: 设备地址 (如 127.0.0.1:5555)

        Returns:
            bool: 是否连接成功
        """
        try:
            result = subprocess.run(
                [self.adb_path, "connect", address],
                capture_output=True,
                timeout=self.timeout,
                encoding='utf-8',
                errors='ignore'
            )

            if "connected" in result.stdout.lower():
                self.logger.info(LogCategory.ADB, "设备连接成功", address=address)
                # 更新连接状态
                self._last_connected_device = address
                self._current_device = address
                return True
            else:
                self.logger.exception(LogCategory.ADB, "设备连接失败",
                                     address=address,
                                     output=result.stdout)
                return False

        except Exception as e:
            self.logger.exception(LogCategory.ADB, "设备连接异常", address=address, error=str(e))
            return False
    
    def disconnect_device(self, address: str) -> bool:
        """断开网络设备连接"""
        try:
            subprocess.run(
                [self.adb_path, "disconnect", address],
                capture_output=True,
                timeout=self.timeout,
                encoding='utf-8',
                errors='ignore'
            )
            self.logger.info(LogCategory.ADB, "设备已断开", address=address)
            # 如果断开的是当前设备，清除当前设备状态
            if self._current_device == address:
                self._current_device = None
            return True
        except Exception as e:
            self.logger.exception(LogCategory.ADB, "设备断开异常", error=str(e))
            return False
    
    def get_device_resolution(self, serial: str) -> Tuple[int, int]:
        """
        获取设备屏幕分辨率
        
        Args:
            serial: 设备序列号
        
        Returns:
            Tuple[int, int]: (width, height)
        """
        try:
            result = subprocess.run(
                [self.adb_path, "-s", serial, "shell", "wm", "size"],
                capture_output=True,
                timeout=self.timeout,
                encoding='utf-8',
                errors='ignore'
            )
            
            if "Physical size:" in result.stdout:
                size_str = result.stdout.split("Physical size:")[1].strip()
                width, height = size_str.split('x')
                return int(width), int(height)
            
            return 0, 0
            
        except Exception as e:
            self.logger.exception(LogCategory.ADB, "获取分辨率异常", serial=serial, error=str(e))
            return 0, 0
    
    def get_device_model(self, serial: str) -> str:
        """获取设备型号"""
        try:
            result = subprocess.run(
                [self.adb_path, "-s", serial, "shell", "getprop", "ro.product.model"],
                capture_output=True,
                timeout=self.timeout,
                encoding='utf-8',
                errors='ignore'
            )
            return result.stdout.strip()
        except Exception as e:
            self.logger.exception(LogCategory.ADB, "获取设备型号异常", error=str(e))
            return ""
    
    def push_file(self, serial: str, local_path: str, remote_path: str) -> bool:
        """推送文件到设备"""
        try:
            result = subprocess.run(
                [self.adb_path, "-s", serial, "push", local_path, remote_path],
                capture_output=True,
                timeout=self.timeout * 3,  # 文件传输可能需要更长时间
                encoding='utf-8',
                errors='ignore'
            )
            if result.returncode == 0:
                self.logger.info(LogCategory.ADB, "文件推送成功",
                                local=local_path, remote=remote_path)
                return True
            return False
        except Exception as e:
            self.logger.exception(LogCategory.ADB, "文件推送异常", error=str(e))
            return False
    
    def pull_file(self, serial: str, remote_path: str, local_path: str) -> bool:
        """从设备拉取文件"""
        try:
            result = subprocess.run(
                [self.adb_path, "-s", serial, "pull", remote_path, local_path],
                capture_output=True,
                timeout=self.timeout * 3,
                encoding='utf-8',
                errors='ignore'
            )
            if result.returncode == 0:
                self.logger.info(LogCategory.ADB, "文件拉取成功",
                                remote=remote_path, local=local_path)
                return True
            return False
        except Exception as e:
            self.logger.exception(LogCategory.ADB, "文件拉取异常", error=str(e))
            return False
    
    def shell_command(self, serial: str, command: str, timeout: int = None, stream: bool = False) -> Tuple[int, str]:
        """
        执行shell命令

        Args:
            serial: 设备序列号
            command: shell命令
            timeout: 超时时间（秒）
            stream: 是否返回流式连接（仅当 adbutils 可用时有效）

        Returns:
            Tuple[int, str]: (return_code, output) 或 (AdbConnection, None) 如果 stream=True
        """
        actual_timeout = timeout or self.timeout

        # 如果请求流式并且 adbutils 可用，使用 adbutils
        if stream and self._adb_client:
            try:
                device = self._adb_client.device(serial)
                conn = device.shell(command, stream=True)
                # 返回连接对象，调用者负责读取和关闭
                return conn, None
            except Exception as e:
                self.logger.exception(LogCategory.ADB, "Shell流式命令异常", command=command, error=str(e))
                return -1, ""

        # 否则使用 subprocess
        try:
            result = subprocess.run(
                [self.adb_path, "-s", serial, "shell", command],
                capture_output=True,
                timeout=actual_timeout,
                encoding='utf-8',
                errors='ignore'
            )
            return result.returncode, result.stdout
        except subprocess.TimeoutExpired:
            self.logger.exception(LogCategory.ADB, "Shell命令超时",
                                 command=command, timeout=actual_timeout)
            return -1, ""
        except Exception as e:
            self.logger.exception(LogCategory.ADB, "Shell命令异常", error=str(e))
            return -1, ""

    # ==================== adbutils 集成 ====================

    @property
    def adb(self) -> Optional[AdbClient]:
        """
        获取 adbutils 客户端，用于 scrcpy 的 socket 连接

        Returns:
            Optional[AdbClient]: adbutils 客户端实例
        """
        return self._adb_client

    def create_connection(self, serial: str, network_type: int, name: str) -> socket.socket:
        """
        创建与设备的 socket 连接（scrcpy 使用）

        Args:
            serial: 设备序列号
            network_type: 网络类型（应为 AdbNetwork.LOCAL_ABSTRACT）
            name: 服务名称（如 "scrcpy"）

        Returns:
            socket.socket: 连接成功后的 socket 对象

        Raises:
            AdbError: 连接失败
        """
        if not self._adb_client:
            raise AdbError("adbutils 客户端未初始化")

        # 获取指定设备
        try:
            device = self._adb_client.device(serial)
        except Exception as e:
            raise AdbError(f"获取设备失败: {e}") from e

        # 创建 socket 连接
        # network_type: AdbNetwork.LOCAL_ABSTRACT = 1 (abstract namespace)
        # name: "scrcpy"
        try:
            sock = device.create_connection(network_type, name)
            return sock
        except Exception as e:
            raise AdbError(f"创建 socket 连接失败: {e}") from e

    # ==================== 设备检测（迁移自 StarRailCopilot）====================

    def _get_device_detector(self):
        """延迟初始化设备检测器"""
        if self._detector is None:
            from .device_detector import DeviceDetector
            self._detector = DeviceDetector(self)
        return self._detector

    def get_device_info(self, serial: str) -> Optional[Dict[str, Any]]:
        """
        获取设备完整信息（类型、分辨率、推荐配置）

        Args:
            serial: 设备序列号

        Returns:
            设备信息字典，失败返回 None
        """
        try:
            detector = self._get_device_detector()
            device_info = detector.get_device_info(serial)
            if device_info:
                return {
                    "serial": device_info.serial,
                    "type": device_info.device_type.value,
                    "original_resolution": device_info.original_resolution,
                    "recommended_screenshot": device_info.recommended_screenshot,
                    "recommended_control": device_info.recommended_control,
                    "properties": device_info.properties,
                    "is_emulator": device_info.is_emulator,
                    "is_network_device": device_info.is_network_device
                }
            return None
        except Exception as e:
            self.logger.exception(LogCategory.ADB, "获取设备信息异常", serial=serial, error=str(e))
            return None

    def get_device_type(self, serial: str) -> str:
        """
        获取设备类型

        Args:
            serial: 设备序列号

        Returns:
            设备类型字符串（如 "mumu", "ldplayer"），失败返回 "unknown"
        """
        try:
            detector = self._get_device_detector()
            device_info = detector.get_device_info(serial)
            if device_info:
                return device_info.device_type.value
        except Exception:
            pass
        return "unknown"

    def get_recommended_config(self, serial: str) -> Dict[str, Any]:
        """
        获取设备的推荐配置

        Args:
            serial: 设备序列号

        Returns:
            推荐配置字典，失败返回空字典
        """
        try:
            detector = self._get_device_detector()
            device_info = detector.get_device_info(serial)
            if device_info:
                return detector.get_recommended_config(device_info)
        except Exception:
            pass
        return {}

    def get_last_connected_device(self) -> Optional[str]:
        """
        获取上次成功连接的设备序列号

        Returns:
            Optional[str]: 设备序列号，无记录返回 None
        """
        return self._last_connected_device

    def get_current_device(self) -> Optional[str]:
        """
        获取当前活动设备序列号

        Returns:
            Optional[str]: 设备序列号，无连接返回 None
        """
        return self._current_device