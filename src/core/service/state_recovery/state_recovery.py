"""
状态恢复策略 - 从 DeviceStateManager 拆分

职责：仅负责从异常状态恢复到目标状态
"""

import time
from typing import Dict, Callable

from core.foundation.logger import get_logger, LogCategory, LogLevel


class StateRecoveryStrategy:
    """状态恢复策略 - 管理各状态的恢复方法"""

    def __init__(self, touch_executor=None):
        self.touch_executor = touch_executor
        self.logger = get_logger()

        # 状态 → 恢复策略映射
        self._strategies: Dict[str, Callable] = {
            "unknown": self._recover_from_unknown,
            "error_dialog": self._recover_from_error_dialog,
            "loading_screen": self._recover_from_loading,
            "login_confirm": self._recover_from_login_confirm,
        }

    def recover(self, current_state: str, target_state: str,
                state_detector=None, device_serial: str = "",
                max_attempts: int = 3) -> bool:
        """恢复到目标状态"""
        self.logger.info(LogCategory.ADB,
                        f"状态恢复: {current_state} -> {target_state}")

        if current_state == target_state:
            return True

        for attempt in range(max_attempts):
            self.logger.info(LogCategory.ADB, f"恢复尝试 {attempt + 1}/{max_attempts}")

            strategy = self._strategies.get(current_state, self._recover_from_unknown)
            success = strategy(device_serial, target_state)

            if not success:
                self.logger.warning(LogCategory.ADB, f"恢复策略执行失败: {current_state}")
                time.sleep(1)
                continue

            time.sleep(2)

            if state_detector:
                new_state = state_detector.detect(None, device_serial)
                if new_state == target_state:
                    self.logger.info(LogCategory.ADB,
                                    f"状态恢复成功: {current_state} -> {target_state}")
                    return True
                current_state = new_state

        self.logger.error(LogCategory.ADB,
                         f"状态恢复失败，已尝试 {max_attempts} 次")
        return False

    def _recover_from_unknown(self, device_serial: str, target_state: str) -> bool:
        """未知状态恢复：尝试返回键和点击"""
        self.logger.info(LogCategory.ADB, "执行未知状态恢复")
        if self._press_back():
            time.sleep(1)
        if self._click_center():
            time.sleep(1)
        for _ in range(3):
            if not self._press_back():
                break
            time.sleep(0.5)
        return True

    def _recover_from_error_dialog(self, device_serial: str, target_state: str) -> bool:
        """错误对话框恢复"""
        self.logger.info(LogCategory.ADB, "执行错误对话框恢复")
        if self._click_ratio(0.8, 0.8):
            time.sleep(1)
            return True
        return self._press_back()

    def _recover_from_loading(self, device_serial: str, target_state: str) -> bool:
        """加载界面恢复：等待"""
        self.logger.info(LogCategory.ADB, "执行加载界面恢复")
        time.sleep(3)
        return True

    def _recover_from_login_confirm(self, device_serial: str, target_state: str) -> bool:
        """登录确认界面恢复"""
        self.logger.info(LogCategory.ADB, "执行登录确认界面恢复")
        if self._click_ratio(0.75, 0.75):
            time.sleep(2)
            return True
        return False

    def _press_back(self) -> bool:
        """按返回键"""
        try:
            if self.touch_executor:
                return self.touch_executor.execute_tool_call("press_key", {"key": "back"})
            return False
        except Exception as e:
            self.logger.exception(LogCategory.ADB, f"返回键操作异常: {e}")
            return False

    def _click_center(self) -> bool:
        """点击屏幕中心"""
        return self._click_ratio(0.5, 0.5)

    def _click_ratio(self, x_ratio: float, y_ratio: float) -> bool:
        """按比例点击屏幕"""
        try:
            if self.touch_executor:
                res = self.touch_executor.get_resolution()
                if res != (0, 0):
                    x_px = int(x_ratio * res[0])
                    y_px = int(y_ratio * res[1])
                else:
                    x_px = int(x_ratio * 1920)
                    y_px = int(y_ratio * 1080)
                return self.touch_executor.execute_tool_call("click", {"x": x_px, "y": y_px})
            return False
        except Exception as e:
            self.logger.exception(LogCategory.ADB, f"点击操作异常: {e}")
            return False
