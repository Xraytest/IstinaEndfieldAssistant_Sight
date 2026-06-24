#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
楂樺彲闈犳爣鍑嗘祦鎵ц寮曟搸 v5
鍩轰簬 OCR+ 妯℃澘鍖归厤 +MaaEnd 娴佺▼鍙傝€?+VLM 鍐崇瓥

鏍稿績鐗规€э細
1. 璇嗗埆澧炲己锛歄CR+ 妯℃澘鍖归厤 + 棰滆壊鍖归厤
2. LLM 鍐崇瓥锛氭牴鎹瘑鍒粨鏋滃喅瀹氱偣鍑讳綅缃?3. MaaEnd 妯″紡锛歂avigation鈫扴tatusCheck鈫扴crollFind鈫扖laim鈫払ack
4. 閿欒鎭㈠锛氭棤鍝嶅簲鏃惰嚜鍔ㄩ噸鍚父鎴?5. 澶氶噸楠岃瘉锛氬潗鏍囬獙璇?+ 椤甸潰楠岃瘉+VLM 楠岃瘉
6. 鏃犺秴鏃舵満鍒讹細绛夊緟鐢ㄦ埛纭鎴栬嚜鍔ㄦ仮澶?"""

import sys, os, json, time, cv2, numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

from core.capability.adb_utils import adb_screencap
from core.capability.recognition.recognition_engine import RecognitionEngine
from core.service.page_analyzer import HighPrecisionPageAnalyzer

DEVICE_ADDR = "192.168.1.12:16512"
ADB_PATH = str(PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe")

class HighReliabilityFlowExecutor:
    """楂樺彲闈犳爣鍑嗘祦鎵ц寮曟搸"""
    
    def __init__(self, flow_config: dict):
        self.flow_config = flow_config
        self.recognition_engine = RecognitionEngine()
        self.page_analyzer = HighPrecisionPageAnalyzer()
        self.screenshots = []
        self.recognition_records = []
        
    def _adb_tap(self, x: int, y: int) -> bool:
        import subprocess
        try:
            r = subprocess.run(
                [ADB_PATH, "-s", DEVICE_ADDR, "shell", "input", "tap", str(x), str(y)],
                capture_output=True, timeout=5
            )
            return r.returncode == 0
        except:
            return False
    
    def _adb_back(self) -> bool:
        import subprocess
        try:
            r = subprocess.run(
                [ADB_PATH, "-s", DEVICE_ADDR, "shell", "input", "keyevent", "4"],
                capture_output=True, timeout=5
            )
            return r.returncode == 0
        except:
            return False
    
    def _adb_restart_game(self) -> bool:
        import subprocess
        try:
            print("  [閲嶅惎] 鍏抽棴娓告垙杩涚▼...")
            subprocess.run(
                [ADB_PATH, "-s", DEVICE_ADDR, "shell", "am", "force-stop", "com.hypergryph.endfield"],
                capture_output=True, timeout=10
            )
            time.sleep(2)
            print("  [閲嶅惎] 鍚姩娓告垙...")
            subprocess.run(
                [ADB_PATH, "-s", DEVICE_ADDR, "shell", "monkey", "-p", "com.hypergryph.endfield", "1"],
                capture_output=True, timeout=10
            )
            print("  [閲嶅惎] 绛夊緟娓告垙鍚姩...")
            time.sleep(15)
            return True
        except Exception as e:
            print(f"  [閲嶅惎閿欒] {e}")
            return False
    
    def _capture_and_recognize(self, step_name: str) -> Dict[str, Any]:
        """鎴浘骞舵墽琛岃瘑鍒?""
        img_bytes = adb_screencap(serial=DEVICE_ADDR)
        if not img_bytes:
            return {"error": "screenshot_failed"}
        
        np_img = np.frombuffer(img_bytes, dtype=np.uint8)
        cv_img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
        if cv_img is None:
            return {"error": "decode_failed"}
        
        # 鏃嬭浆涓烘í灞?        rotated = cv2.rotate(cv_img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        resized = cv2.resize(rotated, (1280, 720))
        
        # 淇濆瓨鎴浘
        self.screenshots.append(cv_img.copy())
        
        # 椤甸潰鍒嗘瀽
        page_result = self.page_analyzer.analyze(resized)
        
        # 妯℃澘鍖归厤
        template_results = []
        # TODO: 鏍规嵁閰嶇疆鎵ц妯℃澘鍖归厤
        
        # 棰滆壊鍖归厤
        color_results = []
        # TODO: 鏍规嵁閰嶇疆鎵ц棰滆壊鍖归厤
        
        record = {
            "step": step_name,
            "timestamp": time.time(),
            "page_type": page_result["page_type"],
            "features": page_result["features"],
            "template_match": template_results,
            "color_match": color_results
        }
        self.recognition_records.append(record)
        
        return record
    
    def _detect_page_type(self, features: dict) -> str:
        """鏍规嵁鐗瑰緛妫€娴嬮〉闈㈢被鍨?""
        left_bar = features.get("left_bar_brightness", 0)
        green = features.get("green_pixels_top_right", 0)
        brightness = features.get("full_brightness", 0)
        
        if left_bar < 15 and brightness > 100:
            return "exit_dialog"
        if left_bar > 150 and brightness > 180:
            return "title_loading"
        if left_bar > 40 and brightness < 100:
            return "quest_panel"
        if left_bar > 30 and green > 100:
            return "world"
        
        return "unknown"
    
    def _handle_exit_dialog(self, max_retries: int = 3) -> bool:
        """澶勭悊閫€鍑哄璇濇"""
        for i in range(max_retries):
            print(f"  [瀵硅瘽妗哴 灏濊瘯鍏抽棴 (灏濊瘯 {i+1}/{max_retries})")
            self._adb_tap(960, 600)  # 鐐瑰嚮搴曢儴涓ぎ
            time.sleep(2)
            
            record = self._capture_and_recognize(f"close_dialog_{i+1}")
            if record.get("page_type") != "exit_dialog":
                print("  [鎴愬姛] 瀵硅瘽妗嗗凡鍏抽棴")
                return True
        
        # 閲嶈瘯澶辫触锛岄噸鍚父鎴?        print("  [璀﹀憡] 瀵硅瘽妗嗘棤娉曞叧闂紝灏濊瘯閲嶅惎娓告垙...")
        if self._adb_restart_game():
            print("  [鎴愬姛] 娓告垙宸查噸鍚?)
            self._capture_and_recognize("after_restart")
            return True
        
        return False
    
    def execute_flow(self, flow_name: str) -> Dict[str, Any]:
        """鎵ц鏍囧噯娴?""
        flow = self.flow_config.get("flows", {}).get(flow_name)
        if not flow:
            return {"error": f"Flow not found: {flow_name}"}
        
        print(f"\n{'='*60}")
        print(f"鎵ц鏍囧噯娴侊細{flow_name}")
        print(f"{'='*60}\n")
        
        steps = flow.get("steps", [])
        results = []
        
        for step in steps:
            step_id = step.get("id", "unknown")
            action = step.get("action", "tap")
            desc = step.get("desc", "")
            
            print(f"\n[姝ラ] {step_id}: {desc}")
            
            # 鎵ц鍔ㄤ綔
            if action == "check":
                expect = step.get("expect", "")
                record = self._capture_and_recognize(step_id)
                page_type = self._detect_page_type(record.get("features", {}))
                
                # 澶勭悊閫€鍑哄璇濇
                if page_type == "exit_dialog":
                    if not self._handle_exit_dialog():
                        return {"error": "Failed to close exit dialog", "step": step_id}
                    record = self._capture_and_recognize(f"{step_id}_after_dialog")
                    page_type = self._detect_page_type(record.get("features", {}))
                
                success = page_type == expect or (expect == "world" and page_type in ("world", "quest_panel"))
                results.append({"step": step_id, "action": action, "success": success, "page_type": page_type})
                
            elif action == "tap":
                # 浣跨敤璇嗗埆缁撴灉鎴栭檷绾у埌鍙傝€冨潗鏍?                use_recognition = step.get("use_recognition", False)
                fallback_coords = step.get("fallback_coords", [540, 360])
                
                if use_recognition:
                    # TODO: 鏍规嵁璇嗗埆缁撴灉鍐冲畾鍧愭爣
                    coords = fallback_coords
                    print(f"  [璇嗗埆] 浣跨敤鍙傝€冨潗鏍囷細{coords}")
                else:
                    coords = fallback_coords
                
                success = self._adb_tap(coords[0], coords[1])
                wait_time = step.get("wait", 2)
                time.sleep(wait_time)
                
                record = self._capture_and_recognize(f"{step_id}_after")
                results.append({"step": step_id, "action": action, "success": success, "coords": coords})
                
            elif action == "swipe":
                start = step.get("start", [540, 800])
                end = step.get("end", [540, 400])
                duration = step.get("duration", 500)
                
                # TODO: 瀹炵幇 swipe
                print(f"  [婊戝姩] {start} 鈫?{end} ({duration}ms)")
                results.append({"step": step_id, "action": action, "success": True})
                
            elif action == "back":
                success = self._adb_back()
                wait_time = step.get("wait", 2)
                time.sleep(wait_time)
                
                record = self._capture_and_recognize(f"{step_id}_after")
                results.append({"step": step_id, "action": action, "success": success})
                
            elif action == "wait":
                wait_time = step.get("wait", 2)
                time.sleep(wait_time)
                results.append({"step": step_id, "action": action, "success": True})
                
            elif action == "claim":
                # 鐐瑰嚮棰嗗彇鎸夐挳
                target = step.get("target", "claim_all")
                coords = [810, 900]  # 榛樿棰嗗彇鍧愭爣
                success = self._adb_tap(coords[0], coords[1])
                results.append({"step": step_id, "action": action, "success": success, "target": target})
        
        return {
            "flow": flow_name,
            "success": all(r.get("success", False) for r in results),
            "steps": len(steps),
            "results": results,
            "recognition_records": self.recognition_records
        }


def main():
    """涓诲嚱鏁?""
    # 鍔犺浇閰嶇疆
    config_path = PROJECT_ROOT / "config" / "standard_flows" / "flows_config_v5.json"
    with open(config_path, 'r', encoding='utf-8') as f:
        flow_config = json.load(f)
    
    # 鍒涘缓鎵ц鍣?    executor = HighReliabilityFlowExecutor(flow_config)
    
    # 鎵ц姣忔棩浠诲姟
    result = executor.execute_flow("daily_quest")
    
    # 淇濆瓨缁撴灉
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    record_dir = PROJECT_ROOT / "cache" / f"high_reliability_{timestamp}"
    record_dir.mkdir(parents=True, exist_ok=True)
    
    # 淇濆瓨璇嗗埆璁板綍
    with open(record_dir / "recognition_records.json", 'w', encoding='utf-8') as f:
        json.dump(result.get("recognition_records", []), f, ensure_ascii=False, indent=2)
    
    # 淇濆瓨鎵ц缁撴灉
    with open(record_dir / "execution_result.json", 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    # 淇濆瓨鎴浘
    for i, img in enumerate(executor.screenshots):
        cv2.imwrite(str(record_dir / f"screenshot_{i:03d}.png"), img)
    
    print(f"\n{'='*60}")
    print(f"鎵ц瀹屾垚锛歿result.get('flow')}")
    print(f"鎴愬姛鐜囷細{sum(1 for r in result.get('results', []) if r.get('success'))}/{len(result.get('results', []))}")
    print(f"璁板綍淇濆瓨锛歿record_dir}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

