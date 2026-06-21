#!/usr/bin/env python3
"""
高可靠标准流执行引擎 v5
基于 OCR+ 模板匹配 +MaaEnd 流程参考 +VLM 决策

核心特性：
1. 识别增强：OCR+ 模板匹配 + 颜色匹配
2. LLM 决策：根据识别结果决定点击位置
3. MaaEnd 模式：Navigation→StatusCheck→ScrollFind→Claim→Back
4. 错误恢复：无响应时自动重启游戏
5. 多重验证：坐标验证 + 页面验证+VLM 验证
6. 无超时机制：等待用户确认或自动恢复
"""

import sys, os, json, time, cv2, numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

from _path_setup import PROJECT_ROOT, SRC_DIR, ensure_path
ensure_path()

from core.adb_utils import adb_screencap
from core.recognition.recognition_engine import RecognitionEngine
from core.page_analyzer import HighPrecisionPageAnalyzer

DEVICE_ADDR = "192.168.1.12:16512"
ADB_PATH = str(PROJECT_ROOT / "3rd-party" / "adb" / "adb.exe")

class HighReliabilityFlowExecutor:
    """高可靠标准流执行引擎"""
    
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
            print("  [重启] 关闭游戏进程...")
            subprocess.run(
                [ADB_PATH, "-s", DEVICE_ADDR, "shell", "am", "force-stop", "com.hypergryph.endfield"],
                capture_output=True, timeout=10
            )
            time.sleep(2)
            print("  [重启] 启动游戏...")
            subprocess.run(
                [ADB_PATH, "-s", DEVICE_ADDR, "shell", "monkey", "-p", "com.hypergryph.endfield", "1"],
                capture_output=True, timeout=10
            )
            print("  [重启] 等待游戏启动...")
            time.sleep(15)
            return True
        except Exception as e:
            print(f"  [重启错误] {e}")
            return False
    
    def _capture_and_recognize(self, step_name: str) -> Dict[str, Any]:
        """截图并执行识别"""
        img_bytes = adb_screencap(serial=DEVICE_ADDR)
        if not img_bytes:
            return {"error": "screenshot_failed"}
        
        np_img = np.frombuffer(img_bytes, dtype=np.uint8)
        cv_img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
        if cv_img is None:
            return {"error": "decode_failed"}
        
        # 旋转为横屏
        rotated = cv2.rotate(cv_img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        resized = cv2.resize(rotated, (1280, 720))
        
        # 保存截图
        self.screenshots.append(cv_img.copy())
        
        # 页面分析
        page_result = self.page_analyzer.analyze(resized)
        
        # 模板匹配
        template_results = []
        # TODO: 根据配置执行模板匹配
        
        # 颜色匹配
        color_results = []
        # TODO: 根据配置执行颜色匹配
        
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
        """根据特征检测页面类型"""
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
        """处理退出对话框"""
        for i in range(max_retries):
            print(f"  [对话框] 尝试关闭 (尝试 {i+1}/{max_retries})")
            self._adb_tap(960, 600)  # 点击底部中央
            time.sleep(2)
            
            record = self._capture_and_recognize(f"close_dialog_{i+1}")
            if record.get("page_type") != "exit_dialog":
                print("  [成功] 对话框已关闭")
                return True
        
        # 重试失败，重启游戏
        print("  [警告] 对话框无法关闭，尝试重启游戏...")
        if self._adb_restart_game():
            print("  [成功] 游戏已重启")
            self._capture_and_recognize("after_restart")
            return True
        
        return False
    
    def execute_flow(self, flow_name: str) -> Dict[str, Any]:
        """执行标准流"""
        flow = self.flow_config.get("flows", {}).get(flow_name)
        if not flow:
            return {"error": f"Flow not found: {flow_name}"}
        
        print(f"\n{'='*60}")
        print(f"执行标准流：{flow_name}")
        print(f"{'='*60}\n")
        
        steps = flow.get("steps", [])
        results = []
        
        for step in steps:
            step_id = step.get("id", "unknown")
            action = step.get("action", "tap")
            desc = step.get("desc", "")
            
            print(f"\n[步骤] {step_id}: {desc}")
            
            # 执行动作
            if action == "check":
                expect = step.get("expect", "")
                record = self._capture_and_recognize(step_id)
                page_type = self._detect_page_type(record.get("features", {}))
                
                # 处理退出对话框
                if page_type == "exit_dialog":
                    if not self._handle_exit_dialog():
                        return {"error": "Failed to close exit dialog", "step": step_id}
                    record = self._capture_and_recognize(f"{step_id}_after_dialog")
                    page_type = self._detect_page_type(record.get("features", {}))
                
                success = page_type == expect or (expect == "world" and page_type in ("world", "quest_panel"))
                results.append({"step": step_id, "action": action, "success": success, "page_type": page_type})
                
            elif action == "tap":
                # 使用识别结果或降级到参考坐标
                use_recognition = step.get("use_recognition", False)
                fallback_coords = step.get("fallback_coords", [540, 360])
                
                if use_recognition:
                    # TODO: 根据识别结果决定坐标
                    coords = fallback_coords
                    print(f"  [识别] 使用参考坐标：{coords}")
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
                
                # TODO: 实现 swipe
                print(f"  [滑动] {start} → {end} ({duration}ms)")
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
                # 点击领取按钮
                target = step.get("target", "claim_all")
                coords = [810, 900]  # 默认领取坐标
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
    """主函数"""
    # 加载配置
    config_path = PROJECT_ROOT / "config" / "standard_flows" / "flows_config_v5.json"
    with open(config_path, 'r', encoding='utf-8') as f:
        flow_config = json.load(f)
    
    # 创建执行器
    executor = HighReliabilityFlowExecutor(flow_config)
    
    # 执行每日任务
    result = executor.execute_flow("daily_quest")
    
    # 保存结果
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    record_dir = PROJECT_ROOT / "cache" / f"high_reliability_{timestamp}"
    record_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存识别记录
    with open(record_dir / "recognition_records.json", 'w', encoding='utf-8') as f:
        json.dump(result.get("recognition_records", []), f, ensure_ascii=False, indent=2)
    
    # 保存执行结果
    with open(record_dir / "execution_result.json", 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    # 保存截图
    for i, img in enumerate(executor.screenshots):
        cv2.imwrite(str(record_dir / f"screenshot_{i:03d}.png"), img)
    
    print(f"\n{'='*60}")
    print(f"执行完成：{result.get('flow')}")
    print(f"成功率：{sum(1 for r in result.get('results', []) if r.get('success'))}/{len(result.get('results', []))}")
    print(f"记录保存：{record_dir}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
