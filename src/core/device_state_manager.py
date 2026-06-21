"""
设备状态管理器 - 门面类

组合 StateDetector（状态检测）和 StateRecoveryStrategy（状态恢复）。
"""

from typing import Dict

from core.logger import get_logger, LogCategory, LogLevel
from core.state_detector import StateDetector
from core.state_recovery import StateRecoveryStrategy


class DeviceStateManager:
    """设备状态管理器 - 门面类

    组合 StateDetector 和 StateRecoveryStrategy。
    保持向后兼容的接口。
    """

    TASK_TO_STATE: Dict[str, str] = {
        "task_visit_friends": "game_main",
        "task_game_login": "login_confirm",
        "task_daily_rewards": "game_main",
        "task_delivery_jobs": "game_main",
        "task_seize_entrust": "game_main",
        "task_sell_product": "game_main",
        "task_crafting": "game_main",
        "task_credit_shopping": "game_main",
        "task_weapon_upgrade": "game_main",
        "task_environment_monitoring": "game_main",
    }

    def __init__(self, screen_capture, touch_executor, communicator, auth_manager):
        self.screen_capture = screen_capture
        self.touch_executor = touch_executor
        self.communicator = communicator
        self.auth_manager = auth_manager
        self.logger = get_logger()

        # 组合子模块
        self._detector = StateDetector(communicator=communicator)
        self._recovery = StateRecoveryStrategy(touch_executor=touch_executor)

    # ── 状态检测（委托给 StateDetector） ────────────────────────

    def detect_current_state(self, device_serial: str) -> str:
        """检测当前设备状态"""
        return self._detector.detect(self.screen_capture, device_serial)

    def clear_template_cache(self):
        """清除状态模板缓存"""
        self._detector.clear_cache()

    # ── 状态恢复（委托给 StateRecoveryStrategy） ────────────────

    def recover_to_safe_state(self, device_serial: str,
                              target_state: str = "game_main") -> bool:
        """恢复到安全状态"""
        current_state = self.detect_current_state(device_serial)
        self.logger.info(LogCategory.ADB,
                        f"当前: {current_state}, 目标: {target_state}")

        if current_state == target_state:
            return True

        return self._recovery.recover(
            current_state, target_state,
            state_detector=self._detector,
            device_serial=device_serial,
        )

    def ensure_device_ready(self, device_serial: str, task_id: str) -> bool:
        """确保设备准备好执行任务"""
        self.logger.info(LogCategory.ADB, f"确保设备就绪: {task_id}")
        current_state = self.detect_current_state(device_serial)
        target_state = self.TASK_TO_STATE.get(task_id, "game_main")

        if current_state == target_state:
            return True

        return self.recover_to_safe_state(device_serial, target_state)
