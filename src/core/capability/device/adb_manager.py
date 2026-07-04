"""ADB 设备管理器 - 最简实现

提供 ADB 设备扫描、连接、命令执行和截图能力。
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import List, Optional

from core.foundation.logger import get_logger, LogCategory


class ADBDeviceInfo:
    """ADB 设备信息"""

    def __init__(self, serial: str, state: str = "device"):
        self.serial = serial
        self.state = state

    def __repr__(self) -> str:
        return f"ADBDeviceInfo(serial={self.serial!r}, state={self.state!r})"


class ADBDeviceManager:
    """最简 ADB 设备管理器

    使用 adbutils 或 adb.exe 子进程进行设备管理。
    """

    def __init__(self, adb_path: str = "3rd-part/adb/adb.exe", timeout: int = 10):
        self._adb_path = str(adb_path)
        self._timeout = timeout
        self._logger = get_logger(__name__)

    def _resolve_adb_path(self) -> str:
        """解析 adb 可执行文件路径"""
        adb = Path(self._adb_path)
        if adb.exists():
            return str(adb.resolve())
        return self._adb_path

    def get_devices(self) -> List[ADBDeviceInfo]:
        """获取已连接的 ADB 设备列表"""
        devices: List[ADBDeviceInfo] = []
        try:
            import adbutils

            adb = adbutils.AdbClient(host="127.0.0.1", port=5037)
            for device in adb.devices():
                devices.append(ADBDeviceInfo(serial=device.serial, state=device.state))
            return devices
        except Exception:
            pass
        try:
            output = subprocess.check_output(
                [self._resolve_adb_path(), "devices"],
                text=True,
                timeout=self._timeout,
            )
            for line in output.splitlines()[1:]:
                parts = line.strip().split()
                if len(parts) >= 2:
                    devices.append(ADBDeviceInfo(serial=parts[0], state=parts[1]))
            return devices
        except Exception as e:
            self._logger.error(LogCategory.ADB, "获取设备列表失败", error=str(e))
            return devices

    def shell(self, cmd: str, serial: Optional[str] = None) -> str:
        """执行 ADB shell 命令"""
        try:
            import adbutils

            adb = adbutils.AdbClient(host="127.0.0.1", port=5037)
            device = adb.device(serial=serial or self._first_device_serial())
            if device is None:
                raise RuntimeError("未找到 ADB 设备")
            return device.shell(cmd)
        except Exception:
            return self._shell_via_subprocess(cmd, serial)

    def screencap(self, serial: Optional[str] = None) -> bytes:
        """截图并返回 PNG 二进制数据"""
        try:
            import adbutils

            adb = adbutils.AdbClient(host="127.0.0.1", port=5037)
            device = adb.device(serial=serial or self._first_device_serial())
            if device is None:
                raise RuntimeError("未找到 ADB 设备")
            return device.screencap()
        except Exception:
            return self._screencap_via_subprocess(serial)

    def _first_device_serial(self) -> Optional[str]:
        devices = self.get_devices()
        for device in devices:
            if device.state == "device":
                return device.serial
        return None

    def _shell_via_subprocess(self, cmd: str, serial: Optional[str] = None) -> str:
        adb = self._resolve_adb_path()
        args = [adb]
        if serial:
            args += ["-s", serial]
        args += ["shell", cmd]
        return subprocess.check_output(args, text=True, timeout=self._timeout)

    def run_adb(self, args: List[str], serial: Optional[str] = None) -> str:
        adb = self._resolve_adb_path()
        cmd = [adb]
        if serial:
            cmd += ["-s", serial]
        cmd += args
        return subprocess.check_output(cmd, text=True, timeout=self._timeout)

    def _screencap_via_subprocess(self, serial: Optional[str] = None) -> bytes:
        adb = self._resolve_adb_path()
        args = [adb]
        if serial:
            args += ["-s", serial]
        args += ["shell", "screencap", "-p"]
        return subprocess.check_output(args, timeout=self._timeout)

    def version(self) -> str:
        output = subprocess.check_output([self._resolve_adb_path(), "version"], text=True, timeout=self._timeout)
        return output.strip()
