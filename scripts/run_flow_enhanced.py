#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
??????娴???ц???櫒 v3 - 瀹屾暣?????? OCR + ?姸????満 + 澧炲己 check ?姩浣?

?湪??熷?炶澶?涓婃?ц?屾?????娴?锛屾敮???锛?1. PaddleOCR ?湰?湴璇????
2. ?姸????満??╁?曪?坙oop/check/find_and_click锛?3. 澧炲己???check ?姩浣滐?圤CR + 椤甸潰?????愬櫒??屾ā寮忥??4. 瑙?瑙夊?????
"""

import sys
import os
import argparse
import json
from pathlib import Path
from typing import Dict, Any

from _path_setup import PROJECT_ROOT as _PROJECT_ROOT, SRC_DIR as _SRC_DIR, ensure_path
ensure_path()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"

from standard_flow_engine import FlowConfig, FlowRecorder, Local2BEngine
from core.capability.adb_utils import ADB, adb_screencap, list_devices

# MaaFw 瑙︽帶
try:
    from core.capability.device.touch.maafw_touch_adapter import MaaFwTouchExecutor, MaaFwTouchConfig
    MAAFW_AVAILABLE = True
except ImportError:
    MaaFwTouchExecutor = None
    MAAFW_AVAILABLE = False

# OCR ??岀姸????満
try:
    from core.capability.ocr.ocr_manager import OCRManager
    OCR_MANAGER_AVAILABLE = True
except ImportError:
    OCRManager = None
    OCR_MANAGER_AVAILABLE = False

try:
    from flow_state_machine import FlowStateMachine
    STATE_MACHINE_AVAILABLE = True
except ImportError:
    FlowStateMachine = None
    STATE_MACHINE_AVAILABLE = False


class EnhancedFlowExecutor:
    """澧炲己?????????娴???ц?????- ?????? OCR + ?姸????満"""
    
    def __init__(self, config: FlowConfig, device_serial: str, use_ocr: bool = False, use_state_machine: bool = False):
        self.config = config
        self.device_serial = device_serial
        self.adb = ADB(serial=device_serial)
        self.use_ocr = use_ocr
        self.use_state_machine = use_state_machine
        
        # ??濆?嬪??MaaFw 瑙︽帶
        self._maafw = None
        if MAAFW_AVAILABLE:
            try:
                maafw_config = MaaFwTouchConfig(
                    adb_path=str(PROJECT_ROOT / "3rd-part" / "adb" / "adb.exe"),
                    address=device_serial,
                    screencap_methods=MaaFwTouchConfig.SCREENCAP_ADB_SHELL,
                    input_methods=2,  # MiniTouch
                )
                self._maafw = MaaFwTouchExecutor(maafw_config)
                if self._maafw.connect():
                    print(f"[MaaFw] 瑙︽帶??濆?嬪?栨?愬??锛????杈ㄧ??锛歿self._maafw.get_resolution()}")
                else:
                    print("[MaaFw] 杩炴帴澶辫触")
            except Exception as e:
                print(f"[MaaFw] ??濆?嬪?栧??甯革?歿e}")
        
        # ??濆?嬪??OCR 绠＄?????        self.ocr_manager = None
        if use_ocr and OCR_MANAGER_AVAILABLE:
            try:
                self.ocr_manager = OCRManager()
                print(f"[OCR] OCR 绠＄???櫒??濆?嬪?栨?愬??锛屾ā寮忥?歿self.ocr_manager.ocr_mode}")
            except Exception as e:
                print(f"[OCR] ??濆?嬪?栧け璐ワ?歿e}")
                self.use_ocr = False
        
        # ??濆?嬪?栫姸????満
        self.state_machine = None
        if use_state_machine and STATE_MACHINE_AVAILABLE:
            try:
                self.state_machine = FlowStateMachine(ocr_manager=self.ocr_manager, device_manager=self)
                print(f"[StateMachine] ?姸????満??╁?曞凡?惎???)
            except Exception as e:
                print(f"[StateMachine] ??濆?嬪?栧け璐ワ?歿e}")
                self.use_state_machine = False
    
    def _tap(self, x: int, y: int):
        """??瑰嚮 - 浣跨敤 MaaFw"""
        if self._maafw and self._maafw.connected:
            self._maafw.safe_press(x, y)
        else:
            # ADB ??為??
            import subprocess
            subprocess.run(["adb", "-s", self.device_serial, "shell", "input", "tap", str(x), str(y)])
    
    def _swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300):
        """婊戝姩 - 浣跨敤 MaaFw"""
        if self._maafw and self._maafw.connected:
            self._maafw.safe_swipe(x1, y1, x2, y2, duration)
        else:
            # ADB ??為??
            import subprocess
            subprocess.run(["adb", "-s", self.device_serial, "shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration)])
    
    def _back(self):
        """杩斿?? - 浣跨敤 MaaFw"""
        if self._maafw and self._maafw.connected:
            job = self._maafw.post_keyevent(4)  # KEYCODE_BACK
            if job:
                job.wait()
        else:
            # ADB ??為??
            import subprocess
            subprocess.run(["adb", "-s", self.device_serial, "shell", "input", "keyevent", "4"])
    
    def _check_page_type(self, step_cfg: Dict[str, Any]) -> bool:
        """
        澧炲己???check ?姩浣? - 浣跨敤 OCR + 椤甸潰?????愬??        
        Returns:
            bool: 妫??煡?槸?惁??愬??        """
        success = False
        page_type = "unknown"
        
        # 浼樺??浣跨敤 OCR 绠＄?????        if self.ocr_manager:
            try:
                print(f"  [CHECK] 浣跨敤 OCR 绠＄???櫒妫?娴嬮〉???..")
                state = self.ocr_manager.capture_and_recognize(self.device_serial)
                page_type = state.page_type
                description = state.description
                print(f"  [CHECK] 椤甸潰={page_type} ??忚堪={description}")
                
                expected = step_cfg.get("expect")
                if expected:
                    world_types = ("world", "world_transition", "world_map", "explore")
                    if page_type == expected or (expected == "world" and page_type in world_types):
                        print(f"  [OK] 椤甸潰?尮??嶉?????锛歿expected}")
                        success = True
                    else:
                        print(f"  [WARN] 椤甸潰涓嶅尮??嶏?氭?????={expected} 瀹為??={page_type}")
                else:
                    if page_type not in ("error", "unknown"):
                        success = True
                        print(f"  [OK] 椤甸潰绫诲?嬶?歿page_type}")
                
            except Exception as e:
                print(f"  [WARN] OCR 妫?娴嬪け璐ワ?歿e}")
        
        return success
    
    def execute_flow(self, flow_name: str) -> bool:
        """??ц?屾?????娴?""
        flow_config = self.config.get_flow(flow_name)
        if not flow_config:
            print(f"[ERROR] ?湭?壘??版??绋嬶?歿flow_name}")
            return False
        
        steps = flow_config.get("steps", [])
        nav_coords = self.config.get_variable("nav_coords", {})
        
        print(f"\n{'='*60}")
        print(f"??ц?岋?歿flow_name}")
        print(f"姝ラ锛歿len(steps)}")
        print(f"{'='*60}\n")
        
        all_success = True
        
        for i, step_cfg in enumerate(steps):
            step_id = i + 1
            step_action = step_cfg.get("action", "none")
            step_desc = step_cfg.get("desc", str(step_cfg))
            
            print(f"\n[姝ラ {step_id}/{len(steps)}] {step_desc}")
            print("-" * 50)
            
            success = False
            
            if step_action == "check":
                # 浣跨敤澧炲己???check
                success = self._check_page_type(step_cfg)
            
            elif step_action == "tap":
                coords = step_cfg.get("coords", [540, 360])
                if isinstance(coords, str) and "{{" in coords:
                    var_key = coords.strip("{}")
                    coords = nav_coords.get(var_key, [540, 360])
                
                print(f"  [TAP] {coords}")
                self._tap(coords[0], coords[1])
                self.adb.wait(1)
                success = True
            
            elif step_action == "swipe":
                start = step_cfg.get("start", [200, 1700])
                end = step_cfg.get("end", [200, 1400])
                duration = step_cfg.get("duration", 1000)
                print(f"  [SWIPE] {start} -> {end}")
                self._swipe(start[0], start[1], end[0], end[1], duration)
                self.adb.wait(1)
                success = True
            
            elif step_action == "claim":
                coords = nav_coords.get("claim_all", [810, 900])
                print(f"  [CLAIM] {coords}")
                self._tap(coords[0], coords[1])
                self.adb.wait(2)
                success = True
            
            elif step_action == "back":
                print(f"  [BACK]")
                self._back()
                self.adb.wait(1)
                success = True
            
            elif step_action == "wait":
                duration = step_cfg.get("duration", 2)
                print(f"  [WAIT] {duration}s")
                self.adb.wait(duration)
                success = True
            
            else:
                print(f"  [WARN] ?湭?煡?姩浣滐?歿step_action}")
                success = True
            
            status = "OK" if success else "FAIL"
            print(f"  [{status}]\n")
            
            if not success:
                all_success = False
        
        return all_success


def main():
    parser = argparse.ArgumentParser(description="??????娴???ц???櫒 v3 - 澧炲己???)
    parser.add_argument("--flow", type=str, default="daily_quest", help="娴?绋嬪?嶇О")
    parser.add_argument("--device", type=str, default=None, help="璁惧??搴忓?楀??)
    parser.add_argument("--use-ocr", action="store_true", help="?惎?敤 OCR")
    parser.add_argument("--use-state-machine", action="store_true", help="?惎?敤?姸????満")
    parser.add_argument("--list-devices", action="store_true", help="??楀嚭璁惧??")
    
    args = parser.parse_args()
    
    if args.list_devices:
        devices = list_devices()
        print("?彲?敤璁惧??:")
        for d in devices:
            print(f"  - {d}")
        return 0
    
    device_serial = args.device or list_devices()[0]
    print(f"[璁惧?嘳 {device_serial}")
    
    # 妫??煡杩炴??    adb = ADB(serial=device_serial)
    if not adb.check_connection():
        print(f"[ERROR] 璁惧???湭杩炴??)
        return 1
    
    # ??犺浇??嶇疆
    config = FlowConfig()
    
    # ??涘缓??ц?????    executor = EnhancedFlowExecutor(
        config=config,
        device_serial=device_serial,
        use_ocr=args.use_ocr,
        use_state_machine=args.use_state_machine
    )
    
    # ??ц?屾??绋?
    print(f"\n寮?濮嬫?ц??{args.flow}...")
    success = executor.execute_flow(args.flow)
    
    print(f"\n娴?绋嬪?屾?愶?歿'??愬??' if success else '??夊け璐ユ楠?}")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

