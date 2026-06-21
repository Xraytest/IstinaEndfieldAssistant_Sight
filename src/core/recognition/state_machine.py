#!/usr/bin/env python3
"""
状态机引擎 - MaaEnd 式 DAG 流程执行系统

实现 MaaEnd 的核心流程控制能力：
1. DAG 有向无环图状态机
2. 节点级识别 + 动作执行
3. 条件分支自动路由
4. [JumpBack] 跳转机制
5. 锚点（Anchor）支持

参考：MaaEnd-2/assets/resource/pipeline/
"""

import json
import time
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field
import sys
import os

from utils.paths import get_project_root, get_src_dir, ensure_src_path
ensure_src_path(__file__)

from core.adb_utils import ADB
from core.recognition.recognition_engine import RecognitionEngine, PREDEFINED_STATES


@dataclass
class ExecutionState:
    """执行状态"""
    current_node: str = ""
    anchors: Dict[str, str] = field(default_factory=dict)  # 锚点映射
    step_count: int = 0
    max_steps: int = 100
    history: List[str] = field(default_factory=list)
    result: Dict[str, Any] = field(default_factory=dict)


class StateMachineExecutor:
    """状态机执行引擎"""

    def __init__(self, flow_config: Dict[str, Any], assets_dir: str = None,
                 touch_executor=None):
        """
        初始化执行器

        Args:
            flow_config: 流程配置（JSON 加载的字典）
            assets_dir: 资源目录
            touch_executor: 触控执行器（MaaFwTouchExecutor），用于 click/swipe/keyevent
        """
        self.flow_config = flow_config
        self._touch = touch_executor
        self.adb = ADB()  # 仅用于截图
        self.recognition = RecognitionEngine(assets_dir)
        self.state = ExecutionState()
    
    def execute(self, start_node: str, anchors: Dict[str, str] = None) -> Dict[str, Any]:
        """
        执行流程
        
        Args:
            start_node: 起始节点
            anchors: 锚点映射
            
        Returns:
            执行结果
        """
        self.state = ExecutionState(current_node=start_node, anchors=anchors or {})
        print(f"\n[状态机] 开始执行流程：{start_node}")
        
        while self.state.step_count < self.state.max_steps:
            # 检查循环
            if self.state.current_node in self.state.history[-10:]:
                if self.state.history.count(self.state.current_node) > 5:
                    print(f"[警告] 检测到循环：{self.state.current_node}")
                    break
            
            self.state.history.append(self.state.current_node)
            self.state.step_count += 1
            
            # 执行节点
            success = self._execute_node(self.state.current_node)
            
            if not success:
                print(f"[错误] 节点执行失败：{self.state.current_node}")
                self.state.result["success"] = False
                self.state.result["failed_node"] = self.state.current_node
                return self.state.result
            
            # 检查是否结束
            if self.state.current_node == "StopNode" or "StopTask" in str(self.state.result):
                break
        
        self.state.result["success"] = True
        self.state.result["steps"] = self.state.step_count
        return self.state.result
    
    def _execute_node(self, node_name: str) -> bool:
        """执行单个节点"""
        # 处理锚点跳转
        if node_name.startswith("[Anchor]"):
            anchor_name = node_name[9:]
            if anchor_name in self.state.anchors:
                node_name = self.state.anchors[anchor_name]
                print(f"[锚点] {anchor_name} -> {node_name}")
        
        # 处理跳转回退
        if node_name.startswith("[JumpBack]"):
            actual_node = node_name[11:]
            print(f"[跳转] 回退到：{actual_node}")
            self.state.current_node = actual_node
            return True
        
        # 获取节点配置
        node_config = self.flow_config.get(node_name)
        if not node_config:
            # 检查是否是预定义状态
            if node_name in PREDEFINED_STATES:
                node_config = PREDEFINED_STATES[node_name]
            else:
                print(f"[错误] 节点不存在：{node_name}")
                return False
        
        print(f"[节点 {self.state.step_count}/{self.state.max_steps}] {node_name}: {node_config.get('desc', '')}")

        recog_result = None  # 识别结果（含坐标等）

        # 执行识别
        if "recognition" in node_config:
            success, recog_result = self._execute_recognition(node_config["recognition"])
            if not success:
                print(f"  [识别失败] {node_config.get('desc', '')}")
                # 识别失败，尝试 next 中的备选节点
                next_nodes = node_config.get("next", [])
                if next_nodes:
                    # 处理第一个 next 节点
                    next_node = next_nodes[0]
                    if next_node.startswith("[JumpBack]"):
                        self.state.current_node = next_node[11:]
                    else:
                        self.state.current_node = next_node
                    return True
                else:
                    return False
            else:
                print(f"  [识别成功] {recog_result}")

        # 执行动作
        if "action" in node_config:
            self._execute_action(node_config["action"], recog_result)
        
        # 等待
        if "post_delay" in node_config:
            time.sleep(node_config["post_delay"] / 1000)
        
        # 选择下一个节点
        next_nodes = node_config.get("next", [])
        if next_nodes:
            # 处理锚点
            next_node = next_nodes[0]
            if next_node.startswith("[Anchor]"):
                anchor_name = next_node[9:]
                if anchor_name in self.state.anchors:
                    self.state.current_node = self.state.anchors[anchor_name]
                else:
                    print(f"[警告] 锚点未定义：{anchor_name}")
                    return False
            elif next_node.startswith("[JumpBack]"):
                self.state.current_node = next_node[11:]
            else:
                self.state.current_node = next_node
        else:
            # 没有 next，流程结束
            print(f"[完成] 流程执行完成")
            self.state.current_node = "StopNode"
        
        return True
    
    def _execute_recognition(self, recognition_config: Any) -> Tuple[bool, Any]:
        """执行识别"""
        # 如果是字符串，引用预定义状态
        if isinstance(recognition_config, str):
            if recognition_config in PREDEFINED_STATES:
                recognition_config = PREDEFINED_STATES[recognition_config]
            else:
                # 尝试从 flow_config 中查找
                if recognition_config in self.flow_config:
                    recognition_config = self.flow_config[recognition_config]
                else:
                    return False, None
        
        # 截图
        img_bytes = self.adb.screencap(dedup=False)
        if not img_bytes:
            return False, None
        
        import cv2
        import numpy as np
        img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
        
        # 执行识别
        return self.recognition.recognize(img, recognition_config)
    
    def _get_click_coords(self, action_param: Dict, recog_result: Optional[Dict]) -> Tuple[int, int]:
        """从识别结果或动作参数中提取点击坐标"""
        # 优先使用动作参数中的坐标
        if action_param.get("x") is not None and action_param.get("y") is not None:
            return (action_param["x"], action_param["y"])

        # 从识别结果中提取位置（支持新格式：bbox/center）
        if recog_result:
            # 优先使用 center 字段
            if "center" in recog_result:
                center = recog_result["center"]
                if isinstance(center, (tuple, list)) and len(center) >= 2:
                    return (int(center[0]), int(center[1]))
            
            # 兼容旧格式：location 字段
            if "location" in recog_result:
                loc = recog_result["location"]
                if isinstance(loc, (tuple, list)) and len(loc) >= 2:
                    return (int(loc[0]), int(loc[1]))
            
            # 从 bbox 字段计算中心
            if "bbox" in recog_result:
                bbox = recog_result["bbox"]
                if isinstance(bbox, (tuple, list)) and len(bbox) == 4:
                    x1, y1, x2, y2 = bbox
                    return (int((x1 + x2) / 2), int((y1 + y2) / 2))

        # 从识别结果的 contours 中推算中心位置
        if recog_result and "centers" in recog_result:
            centers = recog_result["centers"]
            if centers and len(centers) > 0:
                return (int(centers[0][0]), int(centers[0][1]))

        # 回退到默认坐标
        return (600, 750)

    def _execute_action(self, action_config: Any, recog_result: Optional[Dict] = None):
        """执行动作"""
        if isinstance(action_config, str):
            action_type = action_config
            action_param = {}
        elif isinstance(action_config, dict):
            action_type = action_config.get("type", "")
            action_param = action_config.get("param", {})
        else:
            return

        if action_type == "Click":
            x, y = self._get_click_coords(action_param, recog_result)
            print(f"  [动作] 点击 ({x}, {y})")
            if self._touch:
                self._touch.click(x, y)
            else:
                print("  [警告] 无触控执行器，跳过点击")
        elif action_type == "Swipe":
            begin = action_param.get("begin", [600, 600])
            end = action_param.get("end", [600, 300])
            duration = action_param.get("duration", 300)
            print(f"  [动作] 滑动 {begin} -> {end}")
            if self._touch:
                self._touch.swipe(begin[0], begin[1], end[0], end[1], duration)
            else:
                print("  [警告] 无触控执行器，跳过滑动")
        elif action_type == "ClickKey":
            key = action_param.get("key", 4)  # 默认返回键
            print(f"  [动作] 按键 {key}")
            if self._touch:
                self._touch.run_pipeline_task(f"Key{key}")
            else:
                print("  [警告] 无触控执行器，跳过按键")
        elif action_type == "StopTask":
            # 停止任务
            print("  [动作] 停止任务")
            self.state.result["stopped"] = True
        elif action_type == "DoNothing":
            # 无操作
            pass
        else:
            print(f"  [警告] 未知动作类型：{action_type}")


# ═══════════════════════════════════════════════════════════════
# 测试：每日任务流程
# ═══════════════════════════════════════════════════════════════

DAILY_QUEST_FLOW = {
    "DailyQuestStart": {
        "desc": "每日任务入口",
        "pre_delay": 0,
        "post_delay": 0,
        "next": [
            "DailyQuestInOperationalManual",
            "[JumpBack]SceneAnyEnterWorld"
        ]
    },
    "DailyQuestInOperationalManual": {
        "desc": "在行动手册界面",
        "recognition": "InOperationalManual",
        "pre_delay": 0,
        "post_delay": 0,
        "next": [
            "DailyQuestEnterTab"
        ]
    },
    "DailyQuestEnterTab": {
        "desc": "进入日常任务标签",
        "recognition": {
            "type": "OCR",
            "roi": [150, 100, 1000, 100],
            "expected": ["日常", "Daily"]
        },
        "action": "Click",
        "post_delay": 1000,
        "next": [
            "DailyQuestClaimLoop",
            "DailyQuestComplete"
        ]
    },
    "DailyQuestClaimLoop": {
        "desc": "领取任务奖励循环",
        "recognition": {
            "type": "OCR",
            "roi": [825, 200, 300, 400],
            "expected": ["领取", "Claim"]
        },
        "action": "Click",
        "post_delay": 400,
        "next": [
            "DailyQuestClaimLoop",  # 继续循环
            "DailyQuestScrollDown"
        ]
    },
    "DailyQuestScrollDown": {
        "desc": "向下滑动",
        "action": {
            "type": "Swipe",
            "begin": [627, 528],
            "end": [627, 238]
        },
        "post_delay": 500,
        "next": [
            "DailyQuestClaimLoop"
        ]
    },
    "DailyQuestComplete": {
        "desc": "完成",
        "action": "DoNothing"
    },
    "SceneAnyEnterWorld": {
        "desc": "进入世界页面",
        "recognition": "InWorld",
        "next": [
            "DailyQuestInOperationalManual",
            "[JumpBack]SceneAnyEnterWorld"
        ]
    }
}


def test_daily_quest():
    """测试每日任务流程"""
    print("\n" + "="*70)
    print("测试：每日任务状态机流程")
    print("="*70)
    
    executor = StateMachineExecutor(DAILY_QUEST_FLOW)
    result = executor.execute("DailyQuestStart")
    
    print("\n[结果]")
    print(f"  成功：{result.get('success', False)}")
    print(f"  步骤：{result.get('steps', 0)}")
    print(f"  历史：{' -> '.join(result.get('history', [])[:10])}")
    
    return result


if __name__ == "__main__":
    test_daily_quest()
