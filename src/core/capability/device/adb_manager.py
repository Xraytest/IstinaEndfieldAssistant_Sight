"""ADB 设备管理器 - 通道职责分工

⚠️ 通道职责（严重红线）：
  - 图像（screencap）：⚠️ 严禁作为生产任务的图像通道！
    严禁使用本类 screencap() 拉取生产任务截图。生产任务统一走 scrcpy
    （_ScrcpySession，见 core/capability/device/android_runtime.py）。
    本 screencap() 仅在 AndroidRuntime 守护进程无法启动 scrcpy 时
    作为极端兜底使用，且调用方必须明确承担延迟 200-500ms 的后果。
  - 触控：本类的 shell() 仅用于非生产 adb shell 命令（如 am start），
    生产任务触控必须走 MaaTouch（MaaEndRuntime._controller.post_*）。
  - shell：仅允许白名单前缀（ALLOWED_SHELL_PREFIXES），防止注入。

提供 ADB 设备扫描、连接、命令执行和极简兜底截图能力。
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional

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

    def screencap(self, serial: Optional[str] = None) -> bytes:
        """⚠️ 极端兜底截图（不推荐作为生产任务图像通道）

        生产任务统一走 scrcpy（android_runtime.py._ScrcpySession）。
        本方法仅在 scrcpy 会话无法启动时作为兜底，调用方必须接受 200-500ms 延迟。
        严禁：把本方法作为生产任务（VisitFriends/AutoCollect 等）的图像通道。
        """
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
        # 防御性校验：理论上调用方已校验，此处再拦截一次避免绕过
        _validate_shell_cmd(cmd)
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
        data = subprocess.check_output(args, timeout=self._timeout)
        # B1/D4: 仅剥离 ADB 在 Windows 下可能插入的「前导 CRLF」；绝不对二进制 PNG
        # 数据做全局 CRLF 替换，否则会破坏 PNG 内部字节导致解码失败。同时校验 PNG 幻数。
        if data[:2] == b"\r\n" and data[2:6] == b"\x89PNG":
            data = data[2:]
        if data[:4] != b"\x89PNG":
            self._logger.warning(LogCategory.ADB, "screencap 返回数据不是合法 PNG", size=len(data))
        return data

    def version(self) -> str:
        output = subprocess.check_output([self._resolve_adb_path(), "version"], text=True, timeout=self._timeout)
        return output.strip()


def _validate_shell_cmd(cmd: str) -> None:
    """校验 shell 命令合法性，非法则抛 ValueError。"""
    if not is_allowed_shell_cmd(cmd):
        raise ValueError(f"shell 命令不在允许的白名单内，已拒绝: {cmd[:80]!r}")
