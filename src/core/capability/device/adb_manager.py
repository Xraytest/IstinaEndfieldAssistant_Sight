"""ADB 设备管理器 - 通道职责分工

⚠️ 通道职责（严重红线）：
  - 图像（screencap）：本类不再提供 screencap 能力。
    生产任务统一走 scrcpy（_ScrcpySession，见 core/capability/device/android_runtime.py）。
  - 触控：本类的 shell() 仅用于非生产 adb shell 命令（如 am start），
    生产任务触控必须走 MaaTouch（MaaEndRuntime._controller.post_*）。
  - shell：仅允许白名单前缀（ALLOWED_SHELL_PREFIXES），防止注入。

提供 ADB 设备扫描、连接、命令执行能力。
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional

from core.foundation.constants import ADB_PATH_DEFAULT
from core.foundation.logger import LogCategory, get_logger
from core.foundation.shell_security import is_allowed_shell_cmd


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

    def __init__(self, adb_path: str = ADB_PATH_DEFAULT, timeout: int = 10):
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
            # 方案 C：adbutils >= 2.0 移除 AdbClient.devices()，改为 device_list()。
            # 同时兼容 1.x（devices）与 2.x（device_list），避免 WARNING 噪音。
            device_iter = getattr(adb, "device_list", None) or getattr(adb, "devices", None)
            if device_iter is None:
                raise RuntimeError("adbutils AdbClient 无 device_list/devices 方法")
            for device in device_iter():
                # adbutils 2.x 移除 AdbDevice.state 属性，改用 get_state() 方法
                _state = getattr(device, "state", None)
                if _state is None and hasattr(device, "get_state"):
                    _state = device.get_state()
                devices.append(ADBDeviceInfo(serial=device.serial, state=_state))
            return devices
        except Exception as e:
            # D3: 不要静默吞掉异常，记录后回退到 subprocess 实现
            self._logger.warning(LogCategory.ADB, "adbutils 获取设备列表失败，回退 subprocess", error=str(e))
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
        """执行 ADB shell 命令

        安全收敛（C-02b）：任何外部传入的 cmd 必须先通过前缀白名单 +
        注入字符校验，否则拒绝执行，避免 `istina shell` 等路径绕过守护进程
        白名单在设备端执行任意命令。
        """
        _validate_shell_cmd(cmd)
        try:
            import adbutils

            adb = adbutils.AdbClient(host="127.0.0.1", port=5037)
            device = adb.device(serial=serial or self._first_device_serial())
            if device is None:
                raise RuntimeError("未找到 ADB 设备")
            return device.shell(cmd)
        except Exception:
            return self._shell_via_subprocess(cmd, serial)

    def _first_device_serial(self) -> Optional[str]:
        devices = self.get_devices()
        for device in devices:
            if device.state == "device":
                return device.serial
        return None

    def _shell_via_subprocess(self, cmd: str, serial: Optional[str] = None) -> str:
        # 防御性校验：理论上调用方已校验，此处再拦截一次避免绕过
        _validate_shell_cmd(cmd)
        adb = self._resolve_adb_path()
        args = [adb]
        if serial:
            args += ["-s", serial]
        args += ["shell", cmd]
        return subprocess.check_output(args, text=True, timeout=self._timeout)

    def run_adb(self, args: List[str], serial: Optional[str] = None) -> str:
        cmd = self.build_adb_cmd(*args, serial=serial)
        return subprocess.check_output(cmd, text=True, timeout=self._timeout)

    def build_adb_cmd(self, *args: str, serial: Optional[str] = None) -> list:
        """构建 adb 命令参数列表（按需含 -s serial）。

        Args:
            args: adb 子命令及其参数（如 "shell", "am", "force-stop", pkg）。
            serial: 设备 serial；为 None 时省略 -s 段（subprocess 调用 adb 时
                仅在多设备场景才需要 -s，单设备时 adb 自动选择）。

        Returns:
            完整的 argv 列表，可直接传给 subprocess.check_output。
        """
        cmd: list = [self._resolve_adb_path()]
        if serial:
            cmd += ["-s", serial]
        cmd += list(args)
        return cmd

    def version(self) -> str:
        output = subprocess.check_output([self._resolve_adb_path(), "version"], text=True, timeout=self._timeout)
        return output.strip()


def _validate_shell_cmd(cmd: str) -> None:
    """校验 shell 命令合法性，非法则抛 ValueError。"""
    if not is_allowed_shell_cmd(cmd):
        raise ValueError(f"shell 命令不在允许的白名单内，已拒绝: {cmd[:80]!r}")
