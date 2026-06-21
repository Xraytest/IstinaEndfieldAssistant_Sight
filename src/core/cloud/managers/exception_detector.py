"""
异常检测器 - 检测明日方舟终末地游戏中的异常情况
"""
import time
import hashlib
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import logging


class ArknightsEndfieldExceptionDetector:
    """明日方舟终末地异常检测器"""
    
    # 游戏特定异常模式
    GAME_SPECIFIC_ERRORS = {
        # 网络相关错误
        "network_error": [
            "网络连接失败", "连接超时", "网络异常", "服务器维护中",
            "正在连接服务器", "请检查网络连接", "网络不稳定"
        ],
        # 游戏加载错误
        "loading_error": [
            "加载失败", "资源加载错误", "游戏资源异常", "数据加载失败",
            "请重新启动游戏", "游戏资源损坏"
        ],
        # 登录错误
        "login_error": [
            "登录失败", "账号密码错误", "账号被封禁", "登录超时",
            "请重新登录", "账号异常", "登录状态失效"
        ],
        # 登录超时弹窗（增强检测）
        "login_timeout": [
            "长时间无操作", "自动登出", "因长时间无操作", "已自动退出",
            "session 过期", "登录已过期", "请重新登录游戏",
            "登录超时", "连接断开", "网络超时",
            "超时", "登出"
        ],
        # 游戏内错误
        "game_error": [
            "游戏异常", "程序错误", "发生错误", "游戏崩溃",
            "请重启游戏", "游戏数据异常", "内存不足"
        ],
        # 维护公告
        "maintenance": [
            "服务器维护", "版本更新", "停机维护", "维护公告",
            "维护中", "即将开服", "维护结束时间"
        ],
        # 弹窗提示
        "popup": [
            "确定", "取消", "关闭", "确认",
            "提示", "警告", "错误", "通知"
        ]
    }
    
    # 界面状态模式（用于检测卡死）
    UI_STATE_PATTERNS = {
        "loading_screen": ["加载中", "正在加载", "Loading", "请稍候"],
        "login_screen": ["登录", "账号", "密码", "开始游戏"],
        "main_menu": ["主界面", "开始游戏", "任务", "邮件", "商店"],
        "game_interface": ["战斗", "关卡", "编队", "基地"],
        "error_screen": ["错误", "失败", "异常", "重试"]
    }
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger("ExceptionDetector")
        self.screenshot_history = []  # 存储最近截图哈希
        self.state_history = []  # 存储界面状态历史
        self.error_counters = {key: 0 for key in self.GAME_SPECIFIC_ERRORS.keys()}
        
    def detect_exceptions_from_screenshot(self, screenshot: np.ndarray, ocr_text: str = "") -> Dict[str, Any]:
        """
        从截图和 OCR 文本中检测异常
        
        Args:
            screenshot: 截图图像 (numpy 数组)
            ocr_text: OCR 识别文本
            
        Returns:
            异常检测结果字典
        """
        results = {
            "has_exception": False,
            "exception_type": None,
            "exception_details": {},
            "recommended_action": None
        }
        
        # 1. 检测文本异常
        text_exceptions = self._detect_text_exceptions(ocr_text)
        if text_exceptions:
            results["has_exception"] = True
            results["exception_type"] = text_exceptions["type"]
            results["exception_details"]["text_matches"] = text_exceptions["matches"]
            results["recommended_action"] = self._get_recommended_action(text_exceptions["type"])
            
        # 2. 检测界面卡死（通过截图哈希变化率）
        # 只有当截图不为 None 时才进行截图相关检测
        if screenshot is not None:
            screenshot_hash = self._calculate_screenshot_hash(screenshot)
            self.screenshot_history.append((time.time(), screenshot_hash))
            
            # 保留最近 30 个截图记录
            if len(self.screenshot_history) > 30:
                self.screenshot_history.pop(0)
                
            # 计算变化率
            if len(self.screenshot_history) >= 10:
                change_rate = self._calculate_change_rate()
                if change_rate < 0.1:  # 变化率低于 10%
                    results["has_exception"] = True
                    results["exception_type"] = "ui_stuck"
                    results["exception_details"]["change_rate"] = change_rate
                    results["exception_details"]["history_size"] = len(self.screenshot_history)
                    results["recommended_action"] = "尝试返回主界面或重启游戏"
        else:
            # 截图为 None 时，只基于文本检测
            pass
            
        # 3. 检测界面状态模式
        ui_state = self._detect_ui_state(ocr_text)
        self.state_history.append((time.time(), ui_state))
        
        # 保留最近 20 个状态记录
        if len(self.state_history) > 20:
            self.state_history.pop(0)
            
        # 检测状态卡死（同一状态持续太久）
        if len(self.state_history) >= 5:
            if self._is_state_stuck():
                results["has_exception"] = True
                results["exception_type"] = "state_stuck"
                results["exception_details"]["stuck_state"] = ui_state
                results["exception_details"]["duration"] = self._get_state_duration(ui_state)
                results["recommended_action"] = "尝试切换界面或执行恢复操作"
                
        return results
    
    def _detect_text_exceptions(self, text: str) -> Optional[Dict]:
        """检测文本中的异常信息"""
        text_lower = text.lower()
        
        for error_type, patterns in self.GAME_SPECIFIC_ERRORS.items():
            matches = []
            for pattern in patterns:
                if pattern.lower() in text_lower:
                    matches.append(pattern)
                    
            if matches:
                return {
                    "type": error_type,
                    "matches": matches,
                    "severity": self._get_error_severity(error_type)
                }
                
        return None
    
    def _calculate_screenshot_hash(self, screenshot: np.ndarray) -> str:
        """计算截图哈希值（简化版）"""
        # 将图像缩小以加速计算
        if screenshot.size > 10000:
            # 取中心区域计算哈希
            h, w = screenshot.shape[:2]
            center = screenshot[h//4:3*h//4, w//4:3*w//4]
            # 转换为灰度并计算哈希
            if len(center.shape) == 3:
                center_gray = np.mean(center, axis=2).astype(np.uint8)
            else:
                center_gray = center
                
            # 计算简单哈希
            flattened = center_gray.flatten()
            return hashlib.md5(flattened.tobytes()).hexdigest()
        else:
            return hashlib.md5(screenshot.tobytes()).hexdigest()
    
    def _calculate_change_rate(self) -> float:
        """计算截图变化率"""
        if len(self.screenshot_history) < 2:
            return 1.0
            
        unique_hashes = len(set(hash for _, hash in self.screenshot_history))
        total_frames = len(self.screenshot_history)
        
        return unique_hashes / total_frames
    
    def _detect_ui_state(self, text: str) -> str:
        """检测界面状态"""
        text_lower = text.lower()
        
        for state, patterns in self.UI_STATE_PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in text_lower:
                    return state
                    
        return "unknown"
    
    def _is_state_stuck(self) -> bool:
        """检测状态是否卡死"""
        if len(self.state_history) < 5:
            return False
            
        # 检查最近 5 个状态是否相同
        recent_states = [state for _, state in self.state_history[-5:]]
        first_state = recent_states[0]
        
        # 所有状态都相同
        if all(state == first_state for state in recent_states):
            # 检查持续时间（超过 30 秒）
            first_time = self.state_history[-5][0]
            last_time = self.state_history[-1][0]
            return (last_time - first_time) > 30
            
        return False
    
    def _get_state_duration(self, state: str) -> float:
        """获取当前状态的持续时间"""
        if not self.state_history:
            return 0.0
            
        current_time = time.time()
        duration = 0.0
        
        # 从后往前计算相同状态的持续时间
        for timestamp, s in reversed(self.state_history):
            if s == state:
                duration = current_time - timestamp
                break
                
        return duration
    
    def _get_error_severity(self, error_type: str) -> str:
        """获取错误严重程度"""
        severity_map = {
            "network_error": "high",
            "loading_error": "medium",
            "login_error": "high",
            "login_timeout": "high",  # 登录超时为高优先级
            "game_error": "critical",
            "maintenance": "info",
            "popup": "low"
        }
        return severity_map.get(error_type, "medium")
    
    def _get_recommended_action(self, error_type: str) -> str:
        """获取推荐操作"""
        action_map = {
            "network_error": "检查网络连接，等待后重试",
            "loading_error": "重启游戏或清理缓存",
            "login_error": "检查账号密码，或等待账号解封",
            "login_timeout": "点击确认按钮关闭弹窗，然后重新登录",  # 登录超时处理
            "game_error": "重启游戏，如持续出现联系客服",
            "maintenance": "等待维护结束",
            "popup": "点击确认/关闭按钮",
            "ui_stuck": "尝试返回主界面或重启游戏",
            "state_stuck": "尝试切换界面或执行恢复操作"
        }
        return action_map.get(error_type, "尝试重启游戏")
    
    def is_login_timeout(self, exception_type: str) -> bool:
        """
        检查是否为登录超时异常
        
        Args:
            exception_type: 异常类型
            
        Returns:
            bool: 是否为登录超时
        """
        return exception_type == "login_timeout"
    
    def reset(self):
        """重置检测器状态"""
        self.screenshot_history.clear()
        self.state_history.clear()
        self.error_counters = {key: 0 for key in self.GAME_SPECIFIC_ERRORS.keys()}
        
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "screenshot_history_size": len(self.screenshot_history),
            "state_history_size": len(self.state_history),
            "error_counters": self.error_counters.copy(),
            "current_change_rate": self._calculate_change_rate() if self.screenshot_history else 0.0
        }


class TaskExecutionMonitor:
    """任务执行监控器"""
    
    def __init__(self, max_iterations_per_task: int = 20, min_change_rate: float = 0.2):
        """
        Args:
            max_iterations_per_task: 每个任务最大迭代次数
            min_change_rate: 最小变化率阈值
        """
        self.max_iterations_per_task = max_iterations_per_task
        self.min_change_rate = min_change_rate
        
        self.task_iterations = {}  # task_id -> iteration_count
        self.task_screenshots = {}  # task_id -> screenshot_hashes
        self.task_start_time = {}  # task_id -> start_time
        
    def track_task_iteration(self, task_id: str, screenshot_hash: str = None) -> Dict[str, Any]:
        """
        跟踪任务迭代
        
        Returns:
            监控结果字典，包含是否应该停止或采取其他行动
        """
        current_time = time.time()
        
        # 初始化任务跟踪
        if task_id not in self.task_iterations:
            self.task_iterations[task_id] = 0
            self.task_screenshots[task_id] = []
            self.task_start_time[task_id] = current_time
            
        # 增加迭代计数
        self.task_iterations[task_id] += 1
        
        # 记录截图哈希
        if screenshot_hash:
            self.task_screenshots[task_id].append(screenshot_hash)
            # 保留最近 10 个哈希
            if len(self.task_screenshots[task_id]) > 10:
                self.task_screenshots[task_id].pop(0)
                
        iteration_count = self.task_iterations[task_id]
        elapsed_time = current_time - self.task_start_time[task_id]
        
        # 检查是否超过最大迭代次数
        if iteration_count >= self.max_iterations_per_task:
            return {
                "should_stop": True,
                "reason": f"达到最大迭代次数 ({self.max_iterations_per_task})",
                "iteration_count": iteration_count,
                "elapsed_time": elapsed_time,
                "action": "跳过当前任务，继续下一个"
            }
            
        # 检查变化率（如果有足够截图）
        if len(self.task_screenshots.get(task_id, [])) >= 5:
            hashes = self.task_screenshots[task_id]
            unique_hashes = len(set(hashes))
            change_rate = unique_hashes / len(hashes)
            
            if change_rate < self.min_change_rate:
                return {
                    "should_stop": True,
                    "reason": f"界面变化率过低 ({change_rate:.2f} < {self.min_change_rate})",
                    "iteration_count": iteration_count,
                    "elapsed_time": elapsed_time,
                    "change_rate": change_rate,
                    "action": "尝试恢复操作或跳过任务"
                }
                
        # 检查执行时间（超过 5 分钟）
        if elapsed_time > 300:  # 5 分钟
            return {
                "should_stop": True,
                "reason": f"任务执行时间过长 ({elapsed_time:.1f}秒)",
                "iteration_count": iteration_count,
                "elapsed_time": elapsed_time,
                "action": "强制跳过当前任务"
            }
            
        return {
            "should_stop": False,
            "iteration_count": iteration_count,
            "elapsed_time": elapsed_time
        }
    
    def get_iteration_info(self, task_id: str) -> Dict[str, Any]:
        """获取任务迭代信息"""
        if task_id not in self.task_iterations:
            return {}
            
        iteration_count = self.task_iterations[task_id]
        elapsed_time = time.time() - self.task_start_time[task_id]
        hashes = self.task_screenshots.get(task_id, [])
        unique_hashes = len(set(hashes)) if hashes else 0
        change_rate = unique_hashes / len(hashes) if hashes else 0.0
        
        return {
            "iteration_count": iteration_count,
            "elapsed_time": elapsed_time,
            "screenshot_count": len(hashes),
            "unique_screenshots": unique_hashes,
            "change_rate": change_rate
        }
    
    def reset_task(self, task_id: str):
        """重置任务跟踪"""
        if task_id in self.task_iterations:
            del self.task_iterations[task_id]
        if task_id in self.task_screenshots:
            del self.task_screenshots[task_id]
        if task_id in self.task_start_time:
            del self.task_start_time[task_id]
            
    def get_task_statistics(self, task_id: str) -> Dict[str, Any]:
        """获取任务统计信息"""
        if task_id not in self.task_iterations:
            return {}
            
        hashes = self.task_screenshots.get(task_id, [])
        unique_hashes = len(set(hashes)) if hashes else 0
        change_rate = unique_hashes / len(hashes) if hashes else 0.0
        
        return {
            "iteration_count": self.task_iterations[task_id],
            "elapsed_time": time.time() - self.task_start_time[task_id],
            "screenshot_count": len(hashes),
            "unique_screenshots": unique_hashes,
            "change_rate": change_rate
        }
