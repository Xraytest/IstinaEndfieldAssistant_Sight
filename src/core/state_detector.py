"""
状态检测器 - 从 DeviceStateManager 拆分

职责：仅负责设备状态检测和模板匹配
"""

import time
import base64
import io
from typing import Dict, Any, Optional, List, Tuple

from core.logger import get_logger, LogCategory, LogLevel


class StateDetector:
    """状态检测器 - 使用模板匹配检测设备当前状态"""

    # 默认状态模板配置（本地回退）
    DEFAULT_STATE_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
        "game_main": [
            {"path": "Resell/inGame1.png", "threshold": 0.7},
            {"path": "Resell/inGame2.png", "threshold": 0.7},
        ],
        "friend_list": [
            {"path": "VisitFriends/OnFriendList.png", "threshold": 0.7},
        ],
        "login_confirm": [
            {"path": "SceneManager/LoginConfirm.png", "threshold": 0.7},
        ],
        "terminal": [
            {"path": "SceneManager/Terminal.png", "threshold": 0.7},
        ],
        "home_screen": [
            {"path": "SceneManager/HomeScreen.png", "threshold": 0.7},
        ],
        "error_dialog": [
            {"path": "SceneManager/ErrorDialog.png", "threshold": 0.7},
        ],
        "loading_screen": [
            {"path": "SceneManager/LoadingIcon.png", "threshold": 0.7},
        ],
    }

    def __init__(self, communicator=None):
        self.communicator = communicator
        self.logger = get_logger()
        # 模板缓存
        self._state_templates_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._cache_timestamp: float = 0
        self._cache_ttl: float = 300  # 5 分钟

    def detect(self, screen_capture, device_serial: str) -> str:
        """检测设备当前状态"""
        try:
            screenshot_data = screen_capture.capture_screen(device_serial)
            if not screenshot_data:
                self.logger.warning(LogCategory.ADB, "无法获取屏幕截图，返回 unknown")
                return "unknown"

            detected = self._match_state(screenshot_data, device_serial)
            self.logger.info(LogCategory.ADB, f"设备状态检测结果: {detected}")
            return detected

        except Exception as e:
            self.logger.exception(LogCategory.ADB, f"状态检测异常: {e}")
            return "unknown"

    def _match_state(self, screen_data: bytes, device_serial: str) -> str:
        """使用模板匹配检测状态"""
        try:
            from PIL import Image
            import cv2
            import numpy as np

            png_data = base64.b64decode(screen_data) if isinstance(screen_data, str) else screen_data
            image_stream = io.BytesIO(png_data)
            pil_image = Image.open(image_stream)
            opencv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

            templates = self._get_templates()
            if not templates:
                templates = self.DEFAULT_STATE_TEMPLATES

            best_match = "unknown"
            best_score = 0.0

            for state_name, configs in templates.items():
                for cfg in configs:
                    try:
                        template_path = cfg["path"] if isinstance(cfg, dict) else cfg
                        threshold = cfg.get("threshold", 0.7) if isinstance(cfg, dict) else 0.7

                        template_img = self._get_template_image(template_path)
                        if template_img is None:
                            continue

                        result = cv2.matchTemplate(opencv_image, template_img, cv2.TM_CCOEFF_NORMED)
                        _, max_val, _, _ = cv2.minMaxLoc(result)

                        if max_val > best_score and max_val > threshold:
                            best_score = max_val
                            best_match = state_name

                    except Exception:
                        continue

            self.logger.debug(LogCategory.ADB, f"模板匹配: {best_match} ({best_score:.2f})")
            return best_match

        except Exception as e:
            self.logger.exception(LogCategory.ADB, f"状态匹配异常: {e}")
            return "unknown"

    def _get_templates(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取状态模板（优先服务端，回退缓存）"""
        if not self.communicator:
            return {}

        current_time = time.time()
        if self._state_templates_cache and (current_time - self._cache_timestamp) < self._cache_ttl:
            return self._state_templates_cache

        try:
            response = self.communicator.send_request("get_state_templates", {})
            if response and response.get("status") == "success":
                templates = response.get("templates", {})
                self._state_templates_cache = templates
                self._cache_timestamp = current_time
                return templates
        except Exception as e:
            self.logger.warning(LogCategory.ADB, f"获取服务端模板失败: {e}")

        return self._state_templates_cache

    def _get_template_image(self, template_path: str) -> Optional[Any]:
        """获取模板图像"""
        if not self.communicator:
            return None

        try:
            import cv2
            import numpy as np

            response = self.communicator.send_request(
                "get_template_image", {"template_path": template_path}
            )
            if response and response.get("status") == "success":
                img_data = response.get("image_data")
                if img_data:
                    img_bytes = base64.b64decode(img_data)
                    nparr = np.frombuffer(img_bytes, np.uint8)
                    return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except Exception:
            pass

        return None

    def clear_cache(self):
        """清除模板缓存"""
        self._state_templates_cache = {}
        self._cache_timestamp = 0
        self.logger.info(LogCategory.ADB, "状态模板缓存已清除")
