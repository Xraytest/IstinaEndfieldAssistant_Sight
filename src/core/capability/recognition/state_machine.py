#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
鐘舵€佹満寮曟搸 - MaaEnd 寮?DAG 娴佺▼鎵ц绯荤粺

瀹炵幇 MaaEnd 鐨勬牳蹇冩祦绋嬫帶鍒惰兘鍔涳細
1. DAG 鏈夊悜鏃犵幆鍥剧姸鎬佹満
2. 鑺傜偣绾ц瘑鍒?+ 鍔ㄤ綔鎵ц
3. 鏉′欢鍒嗘敮鑷姩璺敱
4. [JumpBack] 璺宠浆鏈哄埗
5. 閿氱偣锛圓nchor锛夋敮鎸?

鍙傝€冿細MaaEnd-2/assets/resource/pipeline/
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
    """鎵ц鐘舵€?""
    current_node: str = ""
    anchors: Dict[str, str] = field(default_factory=dict)  # 閿氱偣鏄犲皠
    step_count: int = 0
    max_steps: int = 100
    history: List[str] = field(default_factory=list)
    result: Dict[str, Any] = field(default_factory=dict)


class StateMachineExecutor:
    """鐘舵€佹満鎵ц寮曟搸"""

    def __init__(self, flow_config: Dict[str, Any], assets_dir: str = None,
                 touch_executor=None):
        """
        鍒濆鍖栨墽琛屽櫒

        Args:
            flow_config: 娴佺▼閰嶇疆锛圝SON 鍔犺浇鐨勫瓧鍏革級
            assets_dir: 璧勬簮鐩綍
            touch_executor: 瑙︽帶鎵ц鍣紙MaaFwTouchExecutor锛夛紝鐢ㄤ簬 click/swipe/keyevent
        """
        self.flow_config = flow_config
        self._touch = touch_executor
        self.adb = ADB()  # 浠呯敤浜庢埅鍥?
        self.recognition = RecognitionEngine(assets_dir)
        self.state = ExecutionState()
    
    def execute(self, start_node: str, anchors: Dict[str, str] = None) -> Dict[str, Any]:
        """
        鎵ц娴佺▼
        
        Args:
            start_node: 璧峰鑺傜偣
            anchors: 閿氱偣鏄犲皠
            
        Returns:
            鎵ц缁撴灉
        """
        self.state = ExecutionState(current_node=start_node, anchors=anchors or {})
        print(f"\n[鐘舵€佹満] 寮€濮嬫墽琛屾祦绋嬶細{start_node}")
        
        while self.state.step_count < self.state.max_steps:
            # 妫€鏌ュ惊鐜?
            if self.state.current_node in self.state.history[-10:]:
                if self.state.history.count(self.state.current_node) > 5:
                    print(f"[璀﹀憡] 妫€娴嬪埌寰幆锛歿self.state.current_node}")
                    break
            
            self.state.history.append(self.state.current_node)
            self.state.step_count += 1
            
            # 鎵ц鑺傜偣
            success = self._execute_node(self.state.current_node)
            
            if not success:
                print(f"[閿欒] 鑺傜偣鎵ц澶辫触锛歿self.state.current_node}")
                self.state.result["success"] = False
                self.state.result["failed_node"] = self.state.current_node
                return self.state.result
            
            # 妫€鏌ユ槸鍚︾粨鏉?
            if self.state.current_node == "StopNode" or "StopTask" in str(self.state.result):
                break
        
        self.state.result["success"] = True
        self.state.result["steps"] = self.state.step_count
        return self.state.result
    
    def _execute_node(self, node_name: str) -> bool:
        """鎵ц鍗曚釜鑺傜偣"""
        # 澶勭悊閿氱偣璺宠浆
        if node_name.startswith("[Anchor]"):
            anchor_name = node_name[9:]
            if anchor_name in self.state.anchors:
                node_name = self.state.anchors[anchor_name]
                print(f"[閿氱偣] {anchor_name} -> {node_name}")
        
        # 澶勭悊璺宠浆鍥為€€
        if node_name.startswith("[JumpBack]"):
            actual_node = node_name[11:]
            print(f"[璺宠浆] 鍥為€€鍒帮細{actual_node}")
            self.state.current_node = actual_node
            return True
        
        # 鑾峰彇鑺傜偣閰嶇疆
        node_config = self.flow_config.get(node_name)
        if not node_config:
            # 妫€鏌ユ槸鍚︽槸棰勫畾涔夌姸鎬?
            if node_name in PREDEFINED_STATES:
                node_config = PREDEFINED_STATES[node_name]
            else:
                print(f"[閿欒] 鑺傜偣涓嶅瓨鍦細{node_name}")
                return False
        
        print(f"[鑺傜偣 {self.state.step_count}/{self.state.max_steps}] {node_name}: {node_config.get('desc', '')}")

        recog_result = None  # 璇嗗埆缁撴灉锛堝惈鍧愭爣绛夛級

        # 鎵ц璇嗗埆
        if "recognition" in node_config:
            success, recog_result = self._execute_recognition(node_config["recognition"])
            if not success:
                print(f"  [璇嗗埆澶辫触] {node_config.get('desc', '')}")
                # 璇嗗埆澶辫触锛屽皾璇?next 涓殑澶囬€夎妭鐐?
                next_nodes = node_config.get("next", [])
                if next_nodes:
                    # 澶勭悊绗竴涓?next 鑺傜偣
                    next_node = next_nodes[0]
                    if next_node.startswith("[JumpBack]"):
                        self.state.current_node = next_node[11:]
                    else:
                        self.state.current_node = next_node
                    return True
                else:
                    return False
            else:
                print(f"  [璇嗗埆鎴愬姛] {recog_result}")

        # 鎵ц鍔ㄤ綔
        if "action" in node_config:
            self._execute_action(node_config["action"], recog_result)
        
        # 绛夊緟
        if "post_delay" in node_config:
            time.sleep(node_config["post_delay"] / 1000)
        
        # 閫夋嫨涓嬩竴涓妭鐐?
        next_nodes = node_config.get("next", [])
        if next_nodes:
            # 澶勭悊閿氱偣
            next_node = next_nodes[0]
            if next_node.startswith("[Anchor]"):
                anchor_name = next_node[9:]
                if anchor_name in self.state.anchors:
                    self.state.current_node = self.state.anchors[anchor_name]
                else:
                    print(f"[璀﹀憡] 閿氱偣鏈畾涔夛細{anchor_name}")
                    return False
            elif next_node.startswith("[JumpBack]"):
                self.state.current_node = next_node[11:]
            else:
                self.state.current_node = next_node
        else:
            # 娌℃湁 next锛屾祦绋嬬粨鏉?
            print(f"[瀹屾垚] 娴佺▼鎵ц瀹屾垚")
            self.state.current_node = "StopNode"
        
        return True
    
    def _execute_recognition(self, recognition_config: Any) -> Tuple[bool, Any]:
        """鎵ц璇嗗埆"""
        # 濡傛灉鏄瓧绗︿覆锛屽紩鐢ㄩ瀹氫箟鐘舵€?
        if isinstance(recognition_config, str):
            if recognition_config in PREDEFINED_STATES:
                recognition_config = PREDEFINED_STATES[recognition_config]
            else:
                # 灏濊瘯浠?flow_config 涓煡鎵?
                if recognition_config in self.flow_config:
                    recognition_config = self.flow_config[recognition_config]
                else:
                    return False, None
        
        # 鎴浘
        img_bytes = self.adb.screencap(dedup=False)
        if not img_bytes:
            return False, None
        
        import cv2
        import numpy as np
        img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
        
        # 鎵ц璇嗗埆
        return self.recognition.recognize(img, recognition_config)
    
    def _get_click_coords(self, action_param: Dict, recog_result: Optional[Dict]) -> Tuple[int, int]:
        """浠庤瘑鍒粨鏋滄垨鍔ㄤ綔鍙傛暟涓彁鍙栫偣鍑诲潗鏍?""
        # 浼樺厛浣跨敤鍔ㄤ綔鍙傛暟涓殑鍧愭爣
        if action_param.get("x") is not None and action_param.get("y") is not None:
            return (action_param["x"], action_param["y"])

        # 浠庤瘑鍒粨鏋滀腑鎻愬彇浣嶇疆锛堟敮鎸佹柊鏍煎紡锛歜box/center锛?
        if recog_result:
            # 浼樺厛浣跨敤 center 瀛楁
            if "center" in recog_result:
                center = recog_result["center"]
                if isinstance(center, (tuple, list)) and len(center) >= 2:
                    return (int(center[0]), int(center[1]))
            
            # 鍏煎鏃ф牸寮忥細location 瀛楁
            if "location" in recog_result:
                loc = recog_result["location"]
                if isinstance(loc, (tuple, list)) and len(loc) >= 2:
                    return (int(loc[0]), int(loc[1]))
            
            # 浠?bbox 瀛楁璁＄畻涓績
            if "bbox" in recog_result:
                bbox = recog_result["bbox"]
                if isinstance(bbox, (tuple, list)) and len(bbox) == 4:
                    x1, y1, x2, y2 = bbox
                    return (int((x1 + x2) / 2), int((y1 + y2) / 2))

        # 浠庤瘑鍒粨鏋滅殑 contours 涓帹绠椾腑蹇冧綅缃?
        if recog_result and "centers" in recog_result:
            centers = recog_result["centers"]
            if centers and len(centers) > 0:
                return (int(centers[0][0]), int(centers[0][1]))

        # 鍥為€€鍒伴粯璁ゅ潗鏍?
        return (600, 750)

    def _execute_action(self, action_config: Any, recog_result: Optional[Dict] = None):
        """鎵ц鍔ㄤ綔"""
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
            print(f"  [鍔ㄤ綔] 鐐瑰嚮 ({x}, {y})")
            if self._touch:
                self._touch.click(x, y)
            else:
                print("  [璀﹀憡] 鏃犺Е鎺ф墽琛屽櫒锛岃烦杩囩偣鍑?)
        elif action_type == "Swipe":
            begin = action_param.get("begin", [600, 600])
            end = action_param.get("end", [600, 300])
            duration = action_param.get("duration", 300)
            print(f"  [鍔ㄤ綔] 婊戝姩 {begin} -> {end}")
            if self._touch:
                self._touch.swipe(begin[0], begin[1], end[0], end[1], duration)
            else:
                print("  [璀﹀憡] 鏃犺Е鎺ф墽琛屽櫒锛岃烦杩囨粦鍔?)
        elif action_type == "ClickKey":
            key = action_param.get("key", 4)  # 榛樿杩斿洖閿?
            print(f"  [鍔ㄤ綔] 鎸夐敭 {key}")
            if self._touch:
                self._touch.run_pipeline_task(f"Key{key}")
            else:
                print("  [璀﹀憡] 鏃犺Е鎺ф墽琛屽櫒锛岃烦杩囨寜閿?)
        elif action_type == "StopTask":
            # 鍋滄浠诲姟
            print("  [鍔ㄤ綔] 鍋滄浠诲姟")
            self.state.result["stopped"] = True
        elif action_type == "DoNothing":
            # 鏃犳搷浣?
            pass
        else:
            print(f"  [璀﹀憡] 鏈煡鍔ㄤ綔绫诲瀷锛歿action_type}")


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
# 娴嬭瘯锛氭瘡鏃ヤ换鍔℃祦绋?
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

DAILY_QUEST_FLOW = {
    "DailyQuestStart": {
        "desc": "姣忔棩浠诲姟鍏ュ彛",
        "pre_delay": 0,
        "post_delay": 0,
        "next": [
            "DailyQuestInOperationalManual",
            "[JumpBack]SceneAnyEnterWorld"
        ]
    },
    "DailyQuestInOperationalManual": {
        "desc": "鍦ㄨ鍔ㄦ墜鍐岀晫闈?,
        "recognition": "InOperationalManual",
        "pre_delay": 0,
        "post_delay": 0,
        "next": [
            "DailyQuestEnterTab"
        ]
    },
    "DailyQuestEnterTab": {
        "desc": "杩涘叆鏃ュ父浠诲姟鏍囩",
        "recognition": {
            "type": "OCR",
            "roi": [150, 100, 1000, 100],
            "expected": ["鏃ュ父", "Daily"]
        },
        "action": "Click",
        "post_delay": 1000,
        "next": [
            "DailyQuestClaimLoop",
            "DailyQuestComplete"
        ]
    },
    "DailyQuestClaimLoop": {
        "desc": "棰嗗彇浠诲姟濂栧姳寰幆",
        "recognition": {
            "type": "OCR",
            "roi": [825, 200, 300, 400],
            "expected": ["棰嗗彇", "Claim"]
        },
        "action": "Click",
        "post_delay": 400,
        "next": [
            "DailyQuestClaimLoop",  # 缁х画寰幆
            "DailyQuestScrollDown"
        ]
    },
    "DailyQuestScrollDown": {
        "desc": "鍚戜笅婊戝姩",
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
        "desc": "瀹屾垚",
        "action": "DoNothing"
    },
    "SceneAnyEnterWorld": {
        "desc": "杩涘叆涓栫晫椤甸潰",
        "recognition": "InWorld",
        "next": [
            "DailyQuestInOperationalManual",
            "[JumpBack]SceneAnyEnterWorld"
        ]
    }
}


def test_daily_quest():
    """娴嬭瘯姣忔棩浠诲姟娴佺▼"""
    print("\n" + "="*70)
    print("娴嬭瘯锛氭瘡鏃ヤ换鍔＄姸鎬佹満娴佺▼")
    print("="*70)
    
    executor = StateMachineExecutor(DAILY_QUEST_FLOW)
    result = executor.execute("DailyQuestStart")
    
    print("\n[缁撴灉]")
    print(f"  鎴愬姛锛歿result.get('success', False)}")
    print(f"  姝ラ锛歿result.get('steps', 0)}")
    print(f"  鍘嗗彶锛歿' -> '.join(result.get('history', [])[:10])}")
    
    return result


if __name__ == "__main__":
    test_daily_quest()

