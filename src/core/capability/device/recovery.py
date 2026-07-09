"""异常处理规则模块

提供“无响应重启安卓软件”等恢复策略，供运行时/任务执行时复用。
"""
from __future__ import annotations

import subprocess
import time
from typing import Optional

from core.foundation.logger import LogCategory, get_logger


class AndroidAppRestartPolicy:
    """Android 应用无响应时的重启策略。"""

    def __init__(
        self,
        adb_path: str = "3rd-part/adb/adb.exe",
        package: str = "com.hypergryph.endfield",
        activity: Optional[str] = None,
        wait_after_launch: float = 3.0,
    ):
        self._adb_path = str(adb_path)
        self._package = package
        self._activity = activity
        self._wait_after_launch = wait_after_launch
        self._logger = get_logger(__name__)

    def restart(self, serial: Optional[str] = None) -> bool:
        """重启目标应用。"""
        try:
            self._logger.info(
                LogCategory.MAIN,
                "开始重启 Android 应用",
                package=self._package,
                serial=serial,
            )
            self._force_stop(serial)
            self._clear_canvas(serial)
            self._launch(serial)
            time.sleep(self._wait_after_launch)
            self._logger.info(
                LogCategory.MAIN,
                "Android 应用重启完成",
                package=self._package,
                serial=serial,
            )
            return True
        except Exception as exc:
            self._logger.error(
                LogCategory.MAIN,
                "重启 Android 应用失败",
                package=self._package,
                serial=serial,
                error=str(exc),
            )
            return False

    def _resolve_adb(self, serial: Optional[str]) -> list[str]:
        cmd = [self._adb_path]
        if serial:
            cmd += ["-s", serial]
        return cmd

    def _run(self, args: list[str], serial: Optional[str]) -> None:
        cmd = self._resolve_adb(serial) + args
        subprocess.check_output(cmd, text=True, timeout=30)

    def _force_stop(self, serial: Optional[str]) -> None:
        try:
            self._run(["shell", "am force-stop", self._package], serial)
        except Exception as exc:
            self._logger.warning(
                LogCategory.MAIN,
                "强制停止应用失败，继续尝试",
                package=self._package,
                error=str(exc),
            )

    def _clear_canvas(self, serial: Optional[str]) -> None:
        """清理可能残留的画布/悬浮窗状态。"""
        try:
            self._run(["shell", "wm", "dismiss-keyguard"], serial)
        except Exception:
            pass
        try:
            self._run(["shell", "input", "keyevent", "KEYCODE_WAKEUP"], serial)
        except Exception:
            pass
        try:
            self._run(["shell", "input", "keyevent", "KEYCODE_HOME"], serial)
        except Exception:
            pass

    def _launch(self, serial: Optional[str]) -> None:
        if self._activity:
            try:
                self._run(
                    ["shell", "am", "start", "-n", f"{self._package}/{self._activity}"],
                    serial,
                )
                return
            except Exception as exc:
                self._logger.warning(
                    LogCategory.MAIN,
                    "按 activity 启动失败，回退到 launch",
                    package=self._package,
                    error=str(exc),
                )
        self._run(["shell", "monkey", "-p", self._package, "-c", "android.intent.category.LAUNCHER", "1"], serial)
