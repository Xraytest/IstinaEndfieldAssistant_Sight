"""
ADB设备管理器 - 管理Android设备的ADB连接
"""
import subprocess
import time
import os
from typing import List, Optional, Tuple, Dict, Any

from core.foundation.utils.paths import ensure_src_path
ensure_src_path(__file__)
from core.foundation.logger import get_logger, LogCategory, LogLevel


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
            lines = result.stdout.strip().split('\n')
            for line in lines[1:]:  # 跳过标题行
                if '\t' in line:
                    serial, status = line.split('\t')
                    address = ""
                    if ':' in serial:  # 网络设备
                        address = serial
                    devices.append(AdbDeviceInfo(serial, status, address))
            
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
    
    def shell_command(self, serial: str, command: str, timeout: int = None) -> Tuple[int, str]:
        """
        执行shell命令
        
        Args:
            serial: 设备序列号
            command: shell命令
            timeout: 超时时间（秒）
        
        Returns:
            Tuple[int, str]: (return_code, output)
        """
        actual_timeout = timeout or self.timeout
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