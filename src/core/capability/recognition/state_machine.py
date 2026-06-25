#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
# -*- coding: utf-8 -*-
"""
State Machine Executor - MaaEnd Pipeline DAG execution system

Implements MaaEnd's pipeline workflow capabilities:
1. DAG-directed acyclic graph state machine
2. Node recognition + action execution
3. Condition distribution automatic routing
4. [JumpBack] jump navigation
5. Anchor point support

Reference: MaaEnd-2/assets/resource/pipeline/
"""

import json
import time
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field
import sys
import os

from core.foundation.paths import get_project_root, get_src_dir, ensure_src_path
ensure_src_path(__file__)

from core.capability.adb_utils import ADB
from core.capability.recognition.recognition_engine import RecognitionEngine, PREDEFINED_STATES


@dataclass
class ExecutionState:
    """Execution state"""
    current_node: str = ""
    anchors: Dict[str, str] = field(default_factory=dict)  # Anchor point mapping
    step_count: int = 0
    max_steps: int = 100
    history: List[str] = field(default_factory=list)
    result: Dict[str, Any] = field(default_factory=dict)


class StateMachineExecutor:
    """State machine pipeline executor"""

    def __init__(self, flow_config: Dict[str, Any], assets_dir: str = None,
                 touch_executor=None):
        """
        Initialize executor

        Args:
            flow_config: Flow configuration (JSON loaded dict)
            assets_dir: Assets directory path
            touch_executor: Touch execution object (MaaFwTouchExecutor), used for click/swipe/keyevent
        """
        self.flow_config = flow_config
        self._touch = touch_executor
        self.adb = ADB()  # Used for screenshots
        self.recognition = RecognitionEngine(assets_dir)
        self.state = ExecutionState()
    
    def execute(self, start_node: str, anchors: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Execute flow
        
        Args:
            start_node: Starting node
            anchors: Anchor point mapping
            
        Returns:
            Execution result
        """
        self.state = ExecutionState(current_node=start_node, anchors=anchors or {})
        print(f"\n[State Machine] Start executing flow: {start_node}")
        
        while self.state.step_count < self.state.max_steps:
            # Loop detection
            if self.state.current_node in self.state.history[-10:]:
                if self.state.history.count(self.state.current_node) > 5:
                    print(f"[Warning] Detected loop, stopping: {self.state.current_node}")
                    break
            
            self.state.history.append(self.state.current_node)
            self.state.step_count += 1
            
            # Execute node
            success = self._execute_node(self.state.current_node)
            
            if not success:
                print(f"[Error] Node execution failed: {self.state.current_node}")
                self.state.result["success"] = False
                self.state.result["failed_node"] = self.state.current_node
                return self.state.result
            
            # Check if finished
            if self.state.current_node == "StopNode" or "StopTask" in str(self.state.result):
                break
        
        self.state.result["success"] = True
        self.state.result["steps"] = self.state.step_count
        return self.state.result
    
    def _execute_node(self, node_name: str) -> bool:
        """Execute single node"""
        # Handle anchor jump
        if node_name.startswith("[Anchor]"):
            anchor_name = node_name[9:]
            if anchor_name in self.state.anchors:
                node_name = self.state.anchors[anchor_name]
                print(f"[Anchor] {anchor_name} -> {node_name}")
        
        # Handle return jump
        if node_name.startswith("[JumpBack]"):
            actual_node = node_name[11:]
            print(f"[JumpBack] Return to: {actual_node}")
            self.state.current_node = actual_node
            return True
        
        # Get node config
        node_config = self.flow_config.get(node_name)
        if not node_config:
            # Check if predefined state
            if node_name in PREDEFINED_STATES:
                node_config = PREDEFINED_STATES[node_name]
            else:
                print(f"[Error] Node not found: {node_name}")
                return False
        
        print(f"[Node {self.state.step_count}/{self.state.max_steps}] {node_name}: {node_config.get('desc', '')}")

        recog_result = None  # Recognition result (contains bbox)

        # Execute recognition
        if "recognition" in node_config:
            success, recog_result = self._execute_recognition(node_config["recognition"])
            if not success:
                print(f"  [Recognition Failed] {node_config.get('desc', '')}")
                # Recognition failed, take first next node
                next_nodes = node_config.get("next", [])
                if next_nodes:
                    # Take first next node
                    next_node = next_nodes[0]
                    if next_node.startswith("[JumpBack]"):
                        self.state.current_node = next_node[11:]
                    else:
                        self.state.current_node = next_node
                    return True
                else:
                    return False
            else:
                print(f"  [Recognition Success] {recog_result}")

        # Execute action
        if "action" in node_config:
            self._execute_action(node_config["action"], recog_result)
        
        # Delay
        if "post_delay" in node_config:
            time.sleep(node_config["post_delay"] / 1000)
        
        # Select next node
        next_nodes = node_config.get("next", [])
        if next_nodes:
            # Handle anchor
            next_node = next_nodes[0]
            if next_node.startswith("[Anchor]"):
                anchor_name = next_node[9:]
                if anchor_name in self.state.anchors:
                    self.state.current_node = self.state.anchors[anchor_name]
                else:
                    print(f"[Warning] Anchor not defined: {anchor_name}")
                    return False
            elif next_node.startswith("[JumpBack]"):
                self.state.current_node = next_node[11:]
            else:
                self.state.current_node = next_node
        else:
            # No next, flow complete
            print(f"[Complete] Flow execution finished")
            self.state.current_node = "StopNode"
        
        return True
    
    def _execute_recognition(self, recognition_config: Any) -> Tuple[bool, Any]:
        """Execute recognition"""
        # If string, reference predefined state
        if isinstance(recognition_config, str):
            if recognition_config in PREDEFINED_STATES:
                recognition_config = PREDEFINED_STATES[recognition_config]
            else:
                # Try to find in flow_config
                if recognition_config in self.flow_config:
                    recognition_config = self.flow_config[recognition_config]
                else:
                    return False, None
        
        # Capture image
        img_bytes = self.adb.screencap(dedup=False)
        if not img_bytes:
            return False, None
        
        import cv2
        import numpy as np
        img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
        
        # Execute recognition
        return self.recognition.recognize(img, recognition_config)
    
    def _get_click_coords(self, action_param: Dict, recog_result: Optional[Dict]) -> Tuple[int, int]:
        """Get click coordinates from recognition result or action params"""
        # Prefer coordinates from action params
        if action_param.get("x") is not None and action_param.get("y") is not None:
            return (action_param["x"], action_param["y"])

        # Extract coordinates from recognition result (supports new format)
        if recog_result:
            # Prefer center field
            if "center" in recog_result:
                center = recog_result["center"]
                if isinstance(center, (tuple, list)) and len(center) >= 2:
                    return (int(center[0]), int(center[1]))
            
            # Compatible with old format: location field
            if "location" in recog_result:
                loc = recog_result["location"]
                if isinstance(loc, (tuple, list)) and len(loc) >= 2:
                    return (int(loc[0]), int(loc[1]))
            
            # Calculate center from bbox
            if "bbox" in recog_result:
                bbox = recog_result["bbox"]
                if isinstance(bbox, (tuple, list)) and len(bbox) == 4:
                    x1, y1, x2, y2 = bbox
                    return (int((x1 + x2) / 2), int((y1 + y2) / 2))

        # Get first valid coordinate from contours in recognition result
        if recog_result and "centers" in recog_result:
            centers = recog_result["centers"]
            if centers and len(centers) > 0:
                return (int(centers[0][0]), int(centers[0][1]))

        # Return to default coordinates
        return (600, 750)

    def _execute_action(self, action_config: Any, recog_result: Optional[Dict] = None):
        """Execute action"""
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
            print(f"  [Action] Click ({x}, {y})")
            if self._touch:
                self._touch.click(x, y)
            else:
                print("  [Warning] No touch executor, skip click")
        elif action_type == "Swipe":
            begin = action_param.get("begin", [600, 600])
            end = action_param.get("end", [600, 300])
            duration = action_param.get("duration", 300)
            print(f"  [Action] Swipe {begin} -> {end}")
            if self._touch:
                self._touch.swipe(begin[0], begin[1], end[0], end[1], duration)
            else:
                print("  [Warning] No touch executor, skip swipe")
        elif action_type == "ClickKey":
            key = action_param.get("key", 4)  # Default back key
            print(f"  [Action] Press key {key}")
            if self._touch:
                self._touch.run_pipeline_task(f"Key{key}")
            else:
                print("  [Warning] No touch executor, skip key press")
        elif action_type == "StopTask":
            # Stop task
            print("  [Action] Stop task")
            self.state.result["stopped"] = True
        elif action_type == "DoNothing":
            # Do nothing
            pass
        else:
            print(f"  [Warning] Unknown action type: {action_type}")


# ============================================================
# Test: Daily quest flow
# ============================================================

DAILY_QUEST_FLOW = {
    "DailyQuestStart": {
        "desc": "Daily quest task window",
        "pre_delay": 0,
        "post_delay": 0,
        "next": [
            "DailyQuestInOperationalManual",
            "[JumpBack]SceneAnyEnterWorld"
        ]
    },
    "DailyQuestInOperationalManual": {
        "desc": "In game operational manual interface",
        "recognition": "InOperationalManual",
        "pre_delay": 0,
        "post_delay": 0,
        "next": [
            "DailyQuestEnterTab"
        ]
    },
    "DailyQuestEnterTab": {
        "desc": "Enter daily quest tab",
        "recognition": {
            "type": "OCR",
            "roi": [150, 100, 1000, 100],
            "expected": ["Daily", "daily"]
        },
        "action": "Click",
        "post_delay": 1000,
        "next": [
            "DailyQuestClaimLoop",
            "DailyQuestComplete"
        ]
    },
    "DailyQuestClaimLoop": {
        "desc": "Claim quest rewards loop",
        "recognition": {
            "type": "OCR",
            "roi": [825, 200, 300, 400],
            "expected": ["Claim", "claim"]
        },
        "action": "Click",
        "post_delay": 400,
        "next": [
            "DailyQuestClaimLoop",  # Continue loop
            "DailyQuestScrollDown"
        ]
    },
    "DailyQuestScrollDown": {
        "desc": "Scroll down",
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
        "desc": "Complete",
        "action": "DoNothing"
    },
    "SceneAnyEnterWorld": {
        "desc": "Enter world interface",
        "recognition": "InWorld",
        "next": [
            "DailyQuestInOperationalManual",
            "[JumpBack]SceneAnyEnterWorld"
        ]
    }
}


def test_daily_quest():
    """Test daily quest state machine"""
    print("\n" + "="*70)
    print("Test: Daily quest state machine")
    print("="*70)
    
    executor = StateMachineExecutor(DAILY_QUEST_FLOW)
    result = executor.execute("DailyQuestStart")
    
    print("\n[Result]")
    print(f"  Success: {result.get('success', False)}")
    print(f"  Steps: {result.get('steps', 0)}")
    print(f"  History: {' -> '.join(result.get('history', [])[:10])}")
    
    return result


if __name__ == "__main__":
    test_daily_quest()
